type LeagueDateTimeParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
};

const LOCAL_DATE_TIME_PATTERN = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/;

const partsForLeagueTimezone = (
  date: Date,
  timeZone: string,
): LeagueDateTimeParts => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    calendar: "iso8601",
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const lookup = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value);

  return {
    year: lookup("year"),
    month: lookup("month"),
    day: lookup("day"),
    hour: lookup("hour"),
    minute: lookup("minute"),
  };
};

const toLocalInput = ({
  year,
  month,
  day,
  hour,
  minute,
}: LeagueDateTimeParts) =>
  `${year.toString().padStart(4, "0")}-${month.toString().padStart(2, "0")}-${day
    .toString()
    .padStart(2, "0")}T${hour.toString().padStart(2, "0")}:${minute
    .toString()
    .padStart(2, "0")}`;

const parseLocalInput = (value: string): LeagueDateTimeParts | null => {
  const match = LOCAL_DATE_TIME_PATTERN.exec(value);
  if (!match) return null;
  const [year, month, day, hour, minute] = match.slice(1).map(Number);
  const validation = new Date(Date.UTC(year, month - 1, day, hour, minute));
  if (
    validation.getUTCFullYear() !== year ||
    validation.getUTCMonth() !== month - 1 ||
    validation.getUTCDate() !== day ||
    validation.getUTCHours() !== hour ||
    validation.getUTCMinutes() !== minute
  ) {
    return null;
  }
  return { year, month, day, hour, minute };
};

/** Formats a canonical UTC timestamp for a date/time picker in the league timezone. */
export const toLeagueDateTimeLocalValue = (
  value: string | Date | null | undefined,
  timeZone: string,
) => {
  if (!value) return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  try {
    return toLocalInput(partsForLeagueTimezone(date, timeZone));
  } catch {
    return "";
  }
};

/**
 * Resolves a league-local picker value to UTC without relying on the commissioner's
 * browser timezone. Ambiguous and non-existent daylight-saving values are rejected.
 */
export const leagueLocalDateTimeToUtc = (
  value: string,
  timeZone: string,
): { iso: string } | { error: string } => {
  const target = parseLocalInput(value);
  if (!target) return { error: "Choose a valid draft date and time." };

  try {
    // A timezone can differ from UTC by at most 14 hours. Search by minute because a
    // datetime-local input has minute precision, and reject the repeated DST hour.
    const targetAsUtc = Date.UTC(
      target.year,
      target.month - 1,
      target.day,
      target.hour,
      target.minute,
    );
    const matches: Date[] = [];
    const windowMs = 16 * 60 * 60 * 1000;
    for (
      let timestamp = targetAsUtc - windowMs;
      timestamp <= targetAsUtc + windowMs;
      timestamp += 60_000
    ) {
      const candidate = new Date(timestamp);
      if (toLocalInput(partsForLeagueTimezone(candidate, timeZone)) === value) {
        matches.push(candidate);
        if (matches.length > 1) {
          return {
            error:
              "That local time occurs twice because of daylight saving time. Choose another time.",
          };
        }
      }
    }
    if (matches.length !== 1) {
      return {
        error:
          "That local time does not exist because of daylight saving time. Choose another time.",
      };
    }
    return { iso: matches[0].toISOString() };
  } catch {
    return {
      error: "The league timezone is invalid. Refresh the page and try again.",
    };
  }
};

export const formatLeagueDraftDateTime = (
  value: string | Date | null | undefined,
  timeZone: string,
) => {
  if (!value) return "Unavailable";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  try {
    return new Intl.DateTimeFormat(undefined, {
      timeZone,
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return "Unavailable";
  }
};

export const getLeagueTimezoneLabel = (timeZone: string) => {
  try {
    const name = new Intl.DateTimeFormat("en-US", {
      timeZone,
      timeZoneName: "long",
    })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value;
    return name ? `${name} (${timeZone})` : timeZone;
  } catch {
    return timeZone;
  }
};
