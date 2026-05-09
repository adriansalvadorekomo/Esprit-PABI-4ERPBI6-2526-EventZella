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
  readonly isLoggedIn = signal(localStorage.getItem('eventzilla_logged_in') === 'true');
  readonly userEmail  = signal(localStorage.getItem('eventzilla_user_email') ?? '');
  readonly role       = signal(localStorage.getItem('eventzilla_role') ?? '');

  /** Kept for backward-compat (header shows email as badge) */
  get userName() { return this.userEmail; }

  /** Returns null on success, error string on failure */
  signIn(email: string, password: string): string | null {
    const normalised = email.trim().toLowerCase();
    const role = ROLE_BY_EMAIL[normalised];
    if (!role || password !== PASSWORD) {
      return 'Invalid email or password.';
    }
    localStorage.setItem('eventzilla_logged_in', 'true');
    localStorage.setItem('eventzilla_user_email', normalised);
    localStorage.setItem('eventzilla_role', role);
    this.isLoggedIn.set(true);
    this.userEmail.set(normalised);
    this.role.set(role);
    return null;
  }

  signOut(): void {
    localStorage.removeItem('eventzilla_logged_in');
    localStorage.removeItem('eventzilla_user_email');
    localStorage.removeItem('eventzilla_role');
    this.isLoggedIn.set(false);
    this.userEmail.set('');
    this.role.set('');
  }

  get isAdmin(): boolean { return this.role() === 'admin'; }
}
