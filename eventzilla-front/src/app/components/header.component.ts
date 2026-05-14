import { Component, OnInit, OnDestroy, inject, signal, effect } from '@angular/core';
import { ThemeService } from '../services/theme.service';
import { AuthService } from '../services/auth.service';
import { ApiService } from '../services/api.service';
import { N8nAlert } from '../models/ml.models';

@Component({
  selector: 'app-header',
  templateUrl: './header.component.html',
  styleUrl: './header.component.css',
  standalone: false
})
export class HeaderComponent implements OnInit, OnDestroy {
  protected readonly theme = inject(ThemeService);
  protected readonly auth  = inject(AuthService);
  private readonly api    = inject(ApiService);

  showModal  = signal(false);
  menuOpen   = signal(false);
  email      = signal('');
  password   = signal('');
  loginError = signal('');

  // ── Alerts ────────────────────────────────────────────────
  alerts = signal<N8nAlert[]>([]);
  alertsLoading = signal(false);
  unreadAlertCount = signal(0);
  showAlertsModal = signal(false);
  private pollTimer: ReturnType<typeof setInterval> | null = null;

  /** Fetch only the unread count (lightweight, called on init + polling) */
  refreshUnreadCount(): void {
    if (!this.auth.isLoggedIn()) return;
    this.api.getUnreadAlertCount().subscribe({
      next: (res) => this.unreadAlertCount.set(res.unread_count)
    });
  }

  /** Fetch full alerts list + count (called when modal opens) */
  loadAlerts(): void {
    this.alertsLoading.set(true);
    this.api.getAlerts(50).subscribe({
      next: (res) => { this.alerts.set(res); this.alertsLoading.set(false); },
      error: () => this.alertsLoading.set(false)
    });
    this.refreshUnreadCount();
  }

  startPolling(): void {
    this.stopPolling();
    this.pollTimer = setInterval(() => this.refreshUnreadCount(), 30000);
  }

  stopPolling(): void {
    if (this.pollTimer) { clearInterval(this.pollTimer); this.pollTimer = null; }
  }

  toggleAlertsModal(): void {
    this.showAlertsModal.update(v => !v);
    if (this.showAlertsModal()) this.loadAlerts();
  }

  closeAlertsModal(): void {
    this.showAlertsModal.set(false);
  }

  markAlertRead(alert: N8nAlert): void {
    if (alert.is_read) return;
    this.api.markAlertRead(alert.id).subscribe({
      next: () => {
        alert.is_read = true;
        this.unreadAlertCount.update(c => Math.max(0, c - 1));
      }
    });
  }

  alertIcon(severity: string): string {
    const icons: Record<string, string> = { error: '🔴', warning: '🟡', info: '🔵', success: '🟢' };
    return icons[severity] ?? '⚪';
  }

  private onScroll = () => {
    document.querySelector('.header-nav')?.classList.toggle('scrolled', window.scrollY > 10);
  };

  ngOnInit(): void {
    window.addEventListener('scroll', this.onScroll, { passive: true });
    // Auto-fetch alert count immediately on page load
    this.refreshUnreadCount();
    // Poll every 30s for live updates
    this.startPolling();
  }

  ngOnDestroy(): void {
    window.removeEventListener('scroll', this.onScroll);
    this.stopPolling();
  }

  navigate(section: string): void {
    window.location.hash = section;
  }

  openModal():  void { this.showModal.set(true);  this.loginError.set(''); }
  closeModal(): void { this.showModal.set(false); this.email.set(''); this.password.set(''); this.loginError.set(''); }

  submit(): void {
    const err = this.auth.signIn(this.email(), this.password());
    if (err) { this.loginError.set(err); }
    else      { this.closeModal(); window.location.hash = 'lab'; }
  }

  onKeydown(e: KeyboardEvent): void { if (e.key === 'Enter') this.submit(); }
}
