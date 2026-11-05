import Draft from "./Draft";
import { dynastyDraftSource } from "@/hooks/use-dynasty-draft";

/** Same draft screen, backed exclusively by isolated dynasty data. */
export default function DynastyDraft() {
  return <Draft source={dynastyDraftSource} />;
}
