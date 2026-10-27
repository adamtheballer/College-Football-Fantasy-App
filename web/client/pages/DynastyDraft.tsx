import { MembershipGate } from "@/components/MembershipGate";
import Draft from "./Draft";
import { dynastyDraftSource } from "@/hooks/use-dynasty-draft";

/** Same draft screen, backed exclusively by isolated dynasty data. */
export default function DynastyDraft() {
  return <MembershipGate feature="dynasty"><Draft source={dynastyDraftSource} /></MembershipGate>;
}
