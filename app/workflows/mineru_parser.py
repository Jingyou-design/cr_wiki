"""Parse binary company documents through MinerU's precise batch API."""

from __future__ import annotations

import time
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

import httpx

from app.api.schema import MinerUConfig, MinerUDocument


_BATCH_SIZE = 50
_UPLOAD_CHUNK_BYTES = 1024 * 1024
class MinerUConfigurationError(RuntimeError):
    """Raised when MinerU is required but not configured."""


class MinerURequestError(RuntimeError):
    """Raised when MinerU rejects or cannot complete a parse request."""


def parse_documents(
    config: MinerUConfig,
    documents: list[MinerUDocument],
    output_root: Path,
) -> None:
    """Parse documents in batches and write one Markdown file per source."""

    if not documents:
        return
    if not config.api_token.strip():
        raise MinerUConfigurationError(
            "资料包包含 PDF、Word、Excel、PPT 或图片，"
            "但服务器尚未配置 MINERU_API_TOKEN。"
        )

    headers = {"Authorization": f"Bearer {config.api_token.strip()}"}
    timeout = httpx.Timeout(config.request_timeout_seconds)
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        for offset in range(0, len(documents), _BATCH_SIZE):
            batch = documents[offset : offset + _BATCH_SIZE]
            batch_id, upload_urls = _create_batch(client, config, headers, batch)
            for document, upload_url in zip(batch, upload_urls, strict=True):
                _upload_file(client, upload_url, document.source_path)
            results = _wait_for_batch(
                client,
                config,
                headers,
                batch_id,
                batch,
            )
            for document in batch:
                result = results[document.data_id]
                markdown = _download_markdown(client, result["full_zip_url"])
                _write_markdown(output_root, document, markdown)


def _create_batch(
    client: httpx.Client,
    config: MinerUConfig,
    headers: dict[str, str],
    documents: list[MinerUDocument],
) -> tuple[str, list[str]]:
    payload = {
        "files": [
            {
                "name": document.upload_name,
                "data_id": document.data_id,
                "is_ocr": (
                    config.is_ocr
                    if document.source_path.suffix.lower() == ".pdf"
                    else False
                ),
            }
            for document in documents
        ],
        "model_version": config.model_version,
        "language": config.language,
        "enable_table": config.enable_table,
        "enable_formula": config.enable_formula,
    }
    response = _request_json(
        client,
        "POST",
        f"{config.base_url.rstrip('/')}/api/v4/file-urls/batch",
        headers={**headers, "Content-Type": "application/json"},
        json=payload,
    )
    data = _api_data(response, "申请 MinerU 批量上传地址")
    return str(data["batch_id"]), data["file_urls"]


def _upload_file(client: httpx.Client, upload_url: str, path: Path) -> None:
    try:
        response = client.put(
            upload_url,
            headers={"Content-Length": str(path.stat().st_size)},
            content=_file_chunks(path),
        )
        response.raise_for_status()
    except (OSError, httpx.HTTPError) as exc:
        raise MinerURequestError(f"上传到 MinerU 失败：{path.name}。") from exc


def _wait_for_batch(
    client: httpx.Client,
    config: MinerUConfig,
    headers: dict[str, str],
    batch_id: str,
    documents: list[MinerUDocument],
) -> dict[str, dict[str, Any]]:
    expected_ids = {document.data_id for document in documents}
    deadline = time.monotonic() + config.poll_timeout_seconds
    while time.monotonic() < deadline:
        response = _request_json(
            client,
            "GET",
            (
                f"{config.base_url.rstrip('/')}"
                f"/api/v4/extract-results/batch/{batch_id}"
            ),
            headers=headers,
        )
        data = _api_data(response, "查询 MinerU 批量解析状态")
        raw_results = data.get("extract_result", [])
        if not isinstance(raw_results, list):
            raise MinerURequestError("MinerU 返回了无法识别的批量任务状态。")

        by_id: dict[str, dict[str, Any]] = {}
        failures: list[str] = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            data_id = str(raw.get("data_id", "")).strip()
            if not data_id:
                continue
            state = str(raw.get("state", "")).strip()
            if state == "failed":
                failures.append(
                    f"{data_id}：{raw.get('err_msg') or '解析失败'}"
                )
            elif state == "done" and raw.get("full_zip_url"):
                by_id[data_id] = raw

        if failures:
            raise MinerURequestError(
                "MinerU 未能解析部分文件：" + "；".join(failures[:5])
            )
        if expected_ids <= by_id.keys():
            return by_id

        time.sleep(config.poll_interval_seconds)

    raise MinerURequestError(
        f"等待 MinerU 批量任务 {batch_id} 超时，请稍后重试。"
    )


def _download_markdown(
    client: httpx.Client,
    result_url: str,
) -> str:
    try:
        response = client.get(result_url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise MinerURequestError("下载 MinerU 解析结果失败。") from exc

    try:
        with ZipFile(BytesIO(response.content)) as archive:
            candidates = [
                info
                for info in archive.infolist()
                if not info.is_dir()
                and Path(info.filename.replace("\\", "/")).name.casefold()
                == "full.md"
            ]
            if not candidates:
                raise MinerURequestError("MinerU 结果中缺少 full.md。")
            member = candidates[0]
            raw = archive.read(member)
    except (BadZipFile, OSError) as exc:
        raise MinerURequestError("MinerU 结果压缩包损坏。") from exc

    try:
        markdown = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise MinerURequestError("MinerU 生成的 Markdown 不是 UTF-8 编码。") from exc
    if not markdown:
        raise MinerURequestError("MinerU 生成了空 Markdown。")
    return markdown


def _write_markdown(
    output_root: Path,
    document: MinerUDocument,
    markdown: str,
) -> None:
    target = output_root.joinpath(
        *Path(document.target_relative_path.replace("\\", "/")).parts
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise MinerURequestError(
            f"转换结果路径发生冲突：{document.target_relative_path}。"
        )
    target.write_text(markdown + "\n", encoding="utf-8", newline="\n")


def _request_json(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        response = client.request(method, url, **kwargs)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise MinerURequestError("MinerU API 请求失败。") from exc
    if not isinstance(payload, dict):
        raise MinerURequestError("MinerU API 返回了无法识别的数据。")
    return payload


def _api_data(payload: dict[str, Any], action: str) -> dict[str, Any]:
    if payload.get("code") != 0:
        raise MinerURequestError(
            f"{action}失败：{payload.get('msg') or '未知错误'}。"
        )
    data = payload.get("data")
    if not isinstance(data, dict):
        raise MinerURequestError(f"{action}失败：响应中缺少 data。")
    return data


def _file_chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as stream:
        while chunk := stream.read(_UPLOAD_CHUNK_BYTES):
            yield chunk

