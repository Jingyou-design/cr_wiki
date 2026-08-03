import { requirePageUser } from "./auth.js?v=20260730-manager2";
import { createChatController } from "./chat.js?v=20260730-manager2";

const user = await requirePageUser("employee");
if (user) {
  const chat = createChatController({
    userId: user.id,
    configRevision: user.config_revision,
  });
  chat.setReady(true);
}
