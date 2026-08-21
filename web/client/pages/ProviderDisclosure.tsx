import { LegalDocumentLayout, LegalList, LegalSection } from "@/components/legal/LegalDocumentLayout";

export default function ProviderDisclosure() {
  return (
    <LegalDocumentLayout
      title="Provider & Data Disclosure"
      description="How College Football Fantasy uses sports data, availability reports, and internal projections."
    >
      <LegalSection title="Purpose of This Disclosure">
        <p>
          College Football Fantasy uses sports information to power fantasy features. This page distinguishes source statistics,
          the service&apos;s fantasy-scoring calculations, and College Football Fantasy&apos;s internal projections and rankings.
        </p>
      </LegalSection>

      <LegalSection title="Live Scoring">
        <p>
          During the alpha, certain live college-football game and player-stat information may be obtained from publicly accessible
          ESPN data services and processed by College Football Fantasy. The service normalizes source statistics and applies each
          league&apos;s fantasy-scoring rules to calculate displayed fantasy results.
        </p>
        <p>
          Live results may be delayed or revised. Official or provider corrections can change previously displayed fantasy scores,
          matchup results, and standings. ESPN is a trademark of its respective owner. College Football Fantasy is not affiliated
          with or endorsed by ESPN.
        </p>
      </LegalSection>

      <LegalSection title="Official Availability Reports">
        <p>
          Player availability designations may be sourced from publicly released conference or team availability reports for the
          SEC, ACC, Big Ten, and Big 12. College Football Fantasy normalizes those labels for display, but the originating
          organization remains the authoritative source for its report.
        </p>
        <p>
          Availability information is informational only. Status can change before kickoff, and a player listed as available may
          still have limited participation. College Football Fantasy does not diagnose injuries or infer undisclosed medical details.
        </p>
      </LegalSection>

      <LegalSection title="Projections and Rankings">
        <p>
          Pregame projections, live projected final fantasy scores, win probabilities, player values, and rankings are College
          Football Fantasy model outputs. They are estimates generated from available information and modeling; they are not
          official player statistics, guarantees, or betting advice and may change as data changes.
        </p>
      </LegalSection>

      <LegalSection title="Data Freshness and Corrections">
        <LegalList>
          <li>live feeds poll and update periodically rather than instantaneously;</li>
          <li>network or provider delays can occur, and a game&apos;s status can temporarily be stale;</li>
          <li>source statistics may be corrected after they first appear; and</li>
          <li>College Football Fantasy may recalculate fantasy results after accepted corrections.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="Attribution Is Not Endorsement">
        <p>
          Naming a source identifies where information can originate; it does not mean that source endorses, sponsors, partners
          with, or owns College Football Fantasy. This disclosure does not assert licensing rights or an affiliation with any
          conference, university, broadcaster, data provider, or sports organization.
        </p>
      </LegalSection>
    </LegalDocumentLayout>
  );
}
