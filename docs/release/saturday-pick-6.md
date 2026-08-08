# Saturday Pick 6 production enablement

Keep all three flags disabled until an administrator has created a valid Week
contest and its six featured players have verified kickoff times and published
weekly projections:

```dotenv
SATURDAY_PICK_6_ENABLED=true
SATURDAY_PICK_6_PUBLIC_ENABLED=true
SATURDAY_PICK_6_SPONSORS_ENABLED=false
```

Set `SATURDAY_PICK_6_SPONSORS_ENABLED=true` only after sponsor branding, offer
text, disclosure, and reward fulfillment are approved. The API never returns a
sponsor discount code unless the contest is final and the requesting user has a
winning entry.

Creating a contest produces a `SCHEDULED` state. It may be visible as coming
soon but cannot be published or accept picks until all six featured players
have canonical published weekly projections. This intentionally does not derive
weekly figures from season projections.
