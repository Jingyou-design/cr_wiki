from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from app.api.schema import (
    AuthenticatedUserContext,
    DepartmentConfig,
    WorkflowContext,
)
from app.workflows.manager_files import (
    ManagerDirectoryAccessError,
    ManagerFileConflictError,
    ManagerFileNotFoundError,
    create_manager_directory,
    move_manager_path,
    read_manager_file,
    resolve_manager_path,
    scan_manager_file_tree,
    write_manager_file,
)


class ManagerFileTreeTests(TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.context = WorkflowContext(project_root=self.root)
        self.manager = AuthenticatedUserContext(
            user_id="manager-1",
            username="project_manager",
            department_code="project",
            role="manager",
            config_revision="test",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_scans_only_manager_department_source_root(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        (allowed / "项目规范.md").write_text("规范", encoding="utf-8")
        nested = allowed / "进行中"
        nested.mkdir()
        (nested / "项目A.md").write_text("项目A", encoding="utf-8")
        (allowed / ".private.md").write_text("隐藏", encoding="utf-8")

        foreign = self.root / "company-handbook" / "财务部"
        foreign.mkdir()
        (foreign / "财务制度.md").write_text("财务", encoding="utf-8")

        department = DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=[
                "/company-handbook/项目部",
                "/company-handbook/项目部/**",
                "/generated-wiki/drafts/项目部/**",
            ],
        )
        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            response = scan_manager_file_tree(self.context, self.manager)

        self.assertEqual(len(response.roots), 1)
        self.assertEqual(response.roots[0].path, "company-handbook/项目部")
        self.assertEqual(
            [item.name for item in response.roots[0].children],
            ["进行中", "项目规范.md"],
        )

    def test_returns_empty_tree_without_source_read_path(self) -> None:
        department = DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=["/generated-wiki/drafts/项目部/**"],
        )
        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            response = scan_manager_file_tree(self.context, self.manager)

        self.assertEqual(response.roots, [])

    def test_resolves_path_inside_manager_department(self) -> None:
        department = DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=["/company-handbook/项目部/**"],
        )
        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            resolved = resolve_manager_path(
                self.context,
                self.manager,
                "company-handbook/项目部/项目规范.md",
            )

        self.assertEqual(
            resolved,
            (
                self.root
                / "company-handbook"
                / "项目部"
                / "项目规范.md"
            ).resolve(),
        )

    def test_rejects_path_outside_manager_department(self) -> None:
        department = DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=["/company-handbook/项目部/**"],
        )
        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ), self.assertRaises(ManagerDirectoryAccessError):
            resolve_manager_path(
                self.context,
                self.manager,
                "company-handbook/财务部/财务制度.md",
            )

    def test_rejects_parent_traversal_into_foreign_department(self) -> None:
        department = DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=["/company-handbook/项目部/**"],
        )
        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ), self.assertRaises(ManagerDirectoryAccessError):
            resolve_manager_path(
                self.context,
                self.manager,
                "company-handbook/项目部/../财务部/财务制度.md",
            )

    def test_reads_utf8_file(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        target = allowed / "项目规范.md"
        target.write_text("# 项目规范", encoding="utf-8")
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            response = read_manager_file(
                self.context,
                self.manager,
                "company-handbook/项目部/项目规范.md",
            )

        self.assertEqual(response.path, "company-handbook/项目部/项目规范.md")
        self.assertEqual(response.content, "# 项目规范")
        self.assertEqual(response.size, len("# 项目规范".encode("utf-8")))

    def test_creates_and_updates_file(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            created = write_manager_file(
                self.context,
                self.manager,
                "company-handbook/项目部/新项目.md",
                "第一版",
            )
            updated = write_manager_file(
                self.context,
                self.manager,
                "company-handbook/项目部/新项目.md",
                "第二版",
            )

        target = allowed / "新项目.md"
        self.assertEqual(created.status, "created")
        self.assertEqual(updated.status, "updated")
        self.assertEqual(target.read_text(encoding="utf-8"), "第二版")
        self.assertEqual(list(allowed.glob(".*.tmp")), [])

    def test_write_requires_existing_parent_directory(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ), self.assertRaises(ManagerFileNotFoundError):
            write_manager_file(
                self.context,
                self.manager,
                "company-handbook/项目部/不存在/项目.md",
                "内容",
            )

    def test_creates_directory(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            response = create_manager_directory(
                self.context,
                self.manager,
                "company-handbook/项目部/新目录",
            )

        self.assertEqual(response.status, "created")
        self.assertEqual(response.path, "company-handbook/项目部/新目录")
        self.assertTrue((allowed / "新目录").is_dir())

    def test_renames_file(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        source = allowed / "旧名称.md"
        source.write_text("内容", encoding="utf-8")
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ):
            response = move_manager_path(
                self.context,
                self.manager,
                "company-handbook/项目部/旧名称.md",
                "company-handbook/项目部/新名称.md",
            )

        self.assertEqual(response.status, "moved")
        self.assertEqual(response.type, "file")
        self.assertFalse(source.exists())
        self.assertEqual(
            (allowed / "新名称.md").read_text(encoding="utf-8"),
            "内容",
        )

    def test_move_does_not_replace_existing_target(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        (allowed / "源文件.md").write_text("源", encoding="utf-8")
        target = allowed / "目标文件.md"
        target.write_text("目标", encoding="utf-8")
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ), self.assertRaises(ManagerFileConflictError):
            move_manager_path(
                self.context,
                self.manager,
                "company-handbook/项目部/源文件.md",
                "company-handbook/项目部/目标文件.md",
            )

        self.assertEqual(target.read_text(encoding="utf-8"), "目标")

    def test_cannot_move_department_root(self) -> None:
        allowed = self.root / "company-handbook" / "项目部"
        allowed.mkdir(parents=True)
        department = self._project_department()

        with patch(
            "app.workflows.manager_files.department_for",
            return_value=department,
        ), self.assertRaises(ManagerFileConflictError):
            move_manager_path(
                self.context,
                self.manager,
                "company-handbook/项目部",
                "company-handbook/项目部/新位置",
            )

    @staticmethod
    def _project_department() -> DepartmentConfig:
        return DepartmentConfig(
            code="project",
            name="项目部",
            read_paths=["/company-handbook/项目部/**"],
        )
