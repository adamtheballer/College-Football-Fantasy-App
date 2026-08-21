import { LegalDocumentLayout, LegalList, LegalSection } from "@/components/legal/LegalDocumentLayout";

export default function PrivacyPolicy() {
  return (
    <LegalDocumentLayout
      title="Privacy Policy"
      description="How College Football Fantasy processes account, league, and service information."
    >
      <LegalSection title="Introduction">
        <p>
          This Privacy Policy explains how College Football Fantasy processes information when you access the service,
          create an account, participate in a league, or use its fantasy-football features.
        </p>
      </LegalSection>

      <LegalSection title="Information We Collect">
        <p>Information you provide can include your manager name, email address, username, profile picture, and support communications.</p>
        <p>When you use the service, we also process the information needed to operate your fantasy experience, including:</p>
        <LegalList>
          <li>league memberships, team ownership, league settings, and invitations;</li>
          <li>roster and lineup activity, draft history, trades, waiver activity, rivalry choices, and Pick 6 selections when enabled;</li>
          <li>matchup results, fantasy scores, career history, notification preferences and delivery history; and</li>
          <li>chat messages and other content you choose to submit in the service.</li>
        </LegalList>
        <p>
          Passwords are not stored in plaintext. The service uses protected, hash-based credentials for password authentication.
        </p>
      </LegalSection>

      <LegalSection title="Technical Information and Authentication Storage">
        <p>
          The service may process technical and security information such as IP address, browser or user-agent information,
          session information, timestamps, request logs, and security events. This helps authenticate users, protect accounts,
          investigate failures, and maintain the service.
        </p>
        <p>
          The web app uses an HTTP-only refresh-token cookie for session renewal and stores a short-lived access token and its
          expiration in browser storage. It may also store local preferences, such as a selected league or one-time interface
          state. Where push notifications are enabled, the service can process a device or push-subscription identifier to send
          notifications you request.
        </p>
      </LegalSection>

      <LegalSection title="How We Use Information">
        <LegalList>
          <li>provide, authenticate, and secure accounts;</li>
          <li>operate leagues, drafts, rosters, matchups, trades, waivers, and fantasy scoring;</li>
          <li>maintain league and career history;</li>
          <li>send requested in-app, push, or email notifications when those capabilities are enabled;</li>
          <li>provide support, moderate submitted content, prevent abuse, and improve reliability; and</li>
          <li>meet applicable operational and legal obligations.</li>
        </LegalList>
      </LegalSection>

      <LegalSection title="Service Providers and Processing">
        <p>
          College Football Fantasy uses infrastructure providers to host and deliver the web application and API, including Vercel
          for the web application and Railway for application hosting. These providers may process information as needed to run,
          secure, and support the service. Sports-information sources may also provide player, schedule, score, and availability
          information; see the Provider Disclosure for more detail.
        </p>
        <p>
          College Football Fantasy does not sell personal information in the ordinary sense of exchanging it for money.
        </p>
      </LegalSection>

      <LegalSection title="Data Retention">
        <p>
          Information is retained for as long as reasonably necessary to operate the service, maintain legitimate fantasy and
          career history, secure accounts, resolve disputes, and meet applicable obligations. Some league and career history may
          remain as part of a historical league record after an account-related request.
        </p>
      </LegalSection>

      <LegalSection title="Your Choices and Requests">
        <p>
          You can update certain account information and notification preferences from Settings. For appropriate account or data
          requests, contact <a className="font-semibold text-cfb-brand underline underline-offset-4 hover:text-cfb-cyan" href="mailto:absportscfb@gmail.com">absportscfb@gmail.com</a>.
        </p>
      </LegalSection>

      <LegalSection title="Security">
        <p>
          We use administrative, technical, and organizational measures intended to protect account and service information.
          No internet service can promise complete security, so please protect your account credentials and contact us if you
          believe your account has been accessed without authorization.
        </p>
      </LegalSection>

      <LegalSection title="Third-Party Services and Policy Changes">
        <p>
          External sites and providers have their own privacy practices. This policy may change as the service changes; when it
          does, the Last updated date above will be revised.
        </p>
      </LegalSection>
    </LegalDocumentLayout>
  );
}
