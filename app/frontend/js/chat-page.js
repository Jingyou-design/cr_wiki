import { requirePageUser } from "./auth.js?v=20260730-manager2";
import { createChatController } from "./chat.js?v=20260803-chat1";

const user = await requirePageUser("employee");
if (user) {
  const chat = createChatController({
    userId: user.id,
  });
  chat.setReady(true);
}
