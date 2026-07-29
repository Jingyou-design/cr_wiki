import { requirePageUser } from "./auth.js";
import { createChatController } from "./chat.js?v=20260728-2";

const user = await requirePageUser("employee");
if (user) {
  const chat = createChatController(user.config_revision);
  chat.setReady(true);
}
