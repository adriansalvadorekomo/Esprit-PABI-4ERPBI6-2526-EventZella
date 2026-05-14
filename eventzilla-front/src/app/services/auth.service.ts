import { Injectable, signal } from '@angular/core';

const ROLE_BY_EMAIL: Record<string, string> = {
  'marketing@gmail.com':    'marketing',
  'quality@gmail.com':      'quality',
  'operationel@gmail.com':  'operational',
  'business@gmail.com':     'business',
  'karimmakni14@gmail.com': 'admin',
};

const PASSWORD = '12345678';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly storedEmail = (sessionStorage.getItem('eventzilla_user_email') ?? '').toLowerCase();
  private readonly storedRole = sessionStorage.getItem('eventzilla_role') ?? '';
  private readonly hasValidStoredSession =
    sessionStorage.getItem('eventzilla_logged_in') === 'true' &&
    ROLE_BY_EMAIL[this.storedEmail] === this.storedRole;

  readonly isLoggedIn = signal(this.hasValidStoredSession);
  readonly userEmail  = signal(this.hasValidStoredSession ? this.storedEmail : '');
  readonly role       = signal(this.hasValidStoredSession ? this.storedRole : '');

  constructor() {
    if (!this.hasValidStoredSession) {
      this.clearStoredSession();
    }
  }

  /** Kept for backward-compat (header shows email as badge) */
  get userName() { return this.userEmail; }

  /** Returns null on success, error string on failure */
  signIn(email: string, password: string): string | null {
    const normalised = email.trim().toLowerCase();
    const role = ROLE_BY_EMAIL[normalised];
    if (!role || password !== PASSWORD) {
      return 'Invalid email or password.';
    }
    this.clearStoredSession();
    sessionStorage.setItem('eventzilla_logged_in', 'true');
    sessionStorage.setItem('eventzilla_user_email', normalised);
    sessionStorage.setItem('eventzilla_role', role);
    this.isLoggedIn.set(true);
    this.userEmail.set(normalised);
    this.role.set(role);
    return null;
  }

  signOut(): void {
    this.clearStoredSession();
    this.isLoggedIn.set(false);
    this.userEmail.set('');
    this.role.set('');
  }

  private clearStoredSession(): void {
    sessionStorage.removeItem('eventzilla_logged_in');
    sessionStorage.removeItem('eventzilla_user_email');
    sessionStorage.removeItem('eventzilla_role');
    localStorage.removeItem('eventzilla_logged_in');
    localStorage.removeItem('eventzilla_user_email');
    localStorage.removeItem('eventzilla_role');
  }

  get isAdmin(): boolean { return this.role() === 'admin'; }
}
