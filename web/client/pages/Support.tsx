import { LegalDocumentLayout, LegalSection } from "@/components/legal/LegalDocumentLayout";

const SUPPORT_EMAIL = "absportscfb@gmail.com";

/**
 * A release-safe support destination. It deliberately does not depend on the
 * authenticated application runtime, so App Store reviewers and signed-out
 * players can always reach support from the public URL.
 */
export default function Support() {
  return (
    <LegalDocumentLayout
      title="Support"
      description="Contact College Fantasy Football support for account, league, and app help."
    >
      <LegalSection title="Need Help?">
        <p>
          Email College Fantasy Football support for help with your account, league, draft, roster, notifications, or an
          issue in the app.
        </p>
        <p>
          <a
            className="font-semibold text-cfb-brand underline underline-offset-4 hover:text-cfb-cyan"
            href={`mailto:${SUPPORT_EMAIL}`}
          >
            {SUPPORT_EMAIL}
          </a>
        </p>
      </LegalSection>

      <LegalSection title="What to Include">
        <p>
          Please include the email address on your account, the league name when relevant, what you expected to happen,
          what happened instead, and any screenshots that can help us reproduce the issue.
        </p>
      </LegalSection>

      <LegalSection title="Account and Privacy Requests">
        <p>
          For account access, password-reset, deletion, or privacy requests, email the same address from the email
          associated with your College Fantasy Football account whenever possible.
        </p>
      </LegalSection>
    </LegalDocumentLayout>
  );
}
