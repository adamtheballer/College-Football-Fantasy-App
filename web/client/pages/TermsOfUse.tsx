import { Link } from "react-router-dom";

import { LegalDocumentLayout, LegalList, LegalSection } from "@/components/legal/LegalDocumentLayout";

export default function TermsOfUse() {
  return (
    <LegalDocumentLayout
      title="Terms of Use"
      description="Terms for using the College Football Fantasy alpha service."
    >
      <LegalSection title="Acceptance of Terms">
        <p>
          By using College Football Fantasy, you agree to these Terms of Use. If you do not agree, do not use the service.
          These Terms apply alongside any league-specific rules and settings made available in the product.
        </p>
      </LegalSection>

      <LegalSection title="The Service">
        <p>
          College Football Fantasy lets users create or join fantasy leagues, draft college football players, manage rosters,
          compete in matchups, make trades, use waiver and free-agent tools, view projections and player information,
          communicate with league members, and use optional features such as challenges when enabled.
        </p>
      </LegalSection>

      <LegalSection title="Alpha Service">
        <p>
          The service is currently an alpha/pre-release product. Features may change, temporary bugs can occur, data can be
          delayed, availability can change, and service interruptions may happen while the product is improved.
        </p>
      </LegalSection>

      <LegalSection title="Fantasy Scoring and Data Corrections">
        <p>
          Scores can be preliminary while games are active. Provider delays, official corrections, or corrected player statistics
          can change fantasy results, matchup outcomes, and standings. The application&apos;s finalized and corrected data controls
          fantasy results according to the applicable league rules.
        </p>
      </LegalSection>

      <LegalSection title="Fantasy Projections">
        <p>
          Pregame projections, win probabilities, live projected finals, rankings, and player values are estimates generated
          from available data and modeling. They are not guarantees, official statistics, or betting advice.
        </p>
      </LegalSection>

      <LegalSection title="No Wagering">
        <p>College Football Fantasy does not itself provide sports betting or wagering.</p>
      </LegalSection>

      <LegalSection title="Accounts and Acceptable Use">
        <p>You are responsible for providing accurate account information, protecting your credentials, and activity through your account.</p>
        <p>You may not use the service to:</p>
        <LegalList>
          <li>harass, threaten, defraud, impersonate, or spam other people;</li>
          <li>attempt unauthorized access, disrupt the service, or interfere with other users;</li>
          <li>use malicious automation, scrape the service in a way that burdens or bypasses it, or reverse engineer it where prohibited by law; or</li>
          <li>submit illegal, malicious, or abusive content.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="User Content and League Decisions">
        <p>
          You retain ownership of content you submit, such as manager names, league names, profile images, and chat messages.
          You grant College Football Fantasy the limited permission needed to host, process, and display that content to operate
          the service. Private-league managers and commissioners make many league decisions; College Football Fantasy cannot
          guarantee that every disagreement within a league will be resolved by the service operator.
        </p>
      </LegalSection>

      <LegalSection title="Third-Party Information">
        <p>
          Sports and player information may come from third-party or official sources and can change, be corrected, be delayed,
          or be incomplete. Read the <Link className="font-semibold text-cfb-brand underline underline-offset-4 hover:text-cfb-cyan" to="/provider-disclosure">Provider Disclosure</Link> for information about current data sources and how the service uses them.
        </p>
      </LegalSection>

      <LegalSection title="Intellectual Property and Non-Affiliation">
        <p>
          College Football Fantasy&apos;s software, design, branding, and original graphics are protected by applicable law.
          College Football Fantasy does not claim ownership of third-party college names, school trademarks, conference trademarks,
          player names, or provider trademarks.
        </p>
        <p>
          College Football Fantasy is an independent fantasy sports product and is not affiliated with, endorsed by, or sponsored
          by the NCAA, the College Football Playoff, any conference, university, athletics program, broadcaster, or data provider
          unless explicitly stated.
        </p>
      </LegalSection>

      <LegalSection title="Availability, Suspension, and Updates">
        <p>
          The service may change, temporarily stop for maintenance, or remove features that are unsafe or unreliable. We may
          suspend or terminate access that violates these Terms or threatens service integrity. The service is provided as an
          alpha product, and uninterrupted or error-free operation cannot be guaranteed.
        </p>
        <p>These Terms may be updated as the service changes. The Last updated date above identifies the current version.</p>
      </LegalSection>
    </LegalDocumentLayout>
  );
}
