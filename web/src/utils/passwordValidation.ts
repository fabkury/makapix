/**
 * Password validation utility
 * 
 * Requirements:
 * - At least 8 characters long
 * - At least one letter (uppercase or lowercase)
 * - At least one number
 * - Special characters are allowed but not required
 */

export interface PasswordValidationResult {
  isValid: boolean;
  errors: string[];
}

export function validatePassword(password: string): PasswordValidationResult {
  const errors: string[] = [];

  if (!password) {
    errors.push('Password is required');
    return { isValid: false, errors };
  }

  if (password.length < 8) {
    errors.push('Password must be at least 8 characters long');
  }

  const hasLetter = /[a-zA-Z]/.test(password);
  if (!hasLetter) {
    errors.push('Password must contain at least one letter');
  }

  const hasNumber = /[0-9]/.test(password);
  if (!hasNumber) {
    errors.push('Password must contain at least one number');
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

/**
 * Get password strength indication
 */
export function getPasswordStrength(password: string): 'weak' | 'medium' | 'strong' {
  if (password.length < 8) return 'weak';
  
  let strength = 0;
  
  // Length bonus
  if (password.length >= 12) strength += 2;
  else if (password.length >= 10) strength += 1;
  
  // Character variety
  if (/[a-z]/.test(password)) strength += 1;
  if (/[A-Z]/.test(password)) strength += 1;
  if (/[0-9]/.test(password)) strength += 1;
  if (/[^a-zA-Z0-9]/.test(password)) strength += 2; // Special chars bonus
  
  if (strength >= 6) return 'strong';
  if (strength >= 4) return 'medium';
  return 'weak';
}
