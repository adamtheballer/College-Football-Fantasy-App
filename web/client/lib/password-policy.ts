export const PASSWORD_POLICY_MESSAGE =
  "Password must be 12–128 characters and include uppercase, lowercase, number, and special characters.";

export const passwordPolicyChecks = (password: string) => [
  { label: "12+ characters", isValid: password.length >= 12 },
  { label: "128 characters or fewer", isValid: password.length <= 128 },
  { label: "One uppercase letter", isValid: /[A-Z]/.test(password) },
  { label: "One lowercase letter", isValid: /[a-z]/.test(password) },
  { label: "One number", isValid: /\d/.test(password) },
  { label: "One special character", isValid: /[^A-Za-z0-9]/.test(password) },
];

export const passwordMeetsPolicy = (password: string) =>
  passwordPolicyChecks(password).every((check) => check.isValid);

export const validatePasswordChange = (
  currentPassword: string,
  newPassword: string,
  confirmNewPassword: string,
): string | null => {
  if (!currentPassword || !newPassword || !confirmNewPassword) {
    return "Complete every password field.";
  }
  if (!passwordMeetsPolicy(newPassword)) {
    return PASSWORD_POLICY_MESSAGE;
  }
  if (newPassword !== confirmNewPassword) {
    return "New passwords do not match.";
  }
  return null;
};
