import { Component, OnInit, OnDestroy, inject, signal, computed, AfterViewInit, ElementRef } from '@angular/core';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ApiService } from '../services/api.service';
import { AuthService } from '../services/auth.service';
import {
  PricePredictRequest, PricePredictResponse,
  FidelisationRequest, FidelisationResponse,
  LoyaltyRequest, LoyaltyResponse,
  ClusterRequest, ClusterResponse,
  ForecastRequest, ForecastResponse,
  SentimentResponse,
  RecommendationResponse,
  AnomalyResponse, DeepLearningResponse
} from '../models/ml.models';

type Section = 'overview' | 'dashboards' | 'lab' | 'about';
const PROTECTED: Section[] = ['dashboards', 'lab'];

const ALL_MODELS = ['price', 'fidel', 'loyalty', 'cluster', 'forecast', 'revenue', 'sentiment', 'reco', 'anomaly', 'dl'];

const MODELS_BY_ROLE: Record<string, string[]> = {
  marketing:   ['loyalty', 'sentiment', 'reco', 'dl'],
  quality:     ['fidel', 'sentiment', 'anomaly'],
  operational: ['forecast', 'cluster', 'anomaly'],
  business:    ['price', 'revenue', 'dl'],
  admin:       ALL_MODELS,
};

const ROLE_LABELS: Record<string, string> = {
  marketing:   'Marketing Team',
  quality:     'Quality Team',
  operational: 'Operations Team',
  business:    'Business Team',
  admin:       'Administrator',
};

@Component({
  selector: 'app-home',
  templateUrl: './home.component.html',
  styleUrl: './home.component.css',
  standalone: false
})
export class HomeComponent implements OnInit, OnDestroy, AfterViewInit {
  private readonly api       = inject(ApiService);
  private readonly sanitizer = inject(DomSanitizer);
  private readonly el        = inject(ElementRef);
  protected readonly auth    = inject(AuthService);

  readonly pbiUrl     = 'https://app.powerbi.com/reportEmbed?reportId=dc9db629-33f9-4787-871d-12a3eca47048&autoAuth=true&ctid=604f1a96-cbe8-43f8-abbf-f8eaf5d85730';
  readonly pbiUrlSafe: SafeResourceUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.pbiUrl);

  activeSection = signal<Section>('overview');
  selectedModel = signal<string | null>(null);
  modelInfoVisible = signal(false);
  modelInfoKey = signal<string | null>(null);

  readonly filteredModels = computed<string[]>(() => {
    const role = this.auth.role();
    return MODELS_BY_ROLE[role] ?? [];
  });

  readonly roleSubtitle = computed<string>(() => {
    const role = this.auth.role();
    if (!role) return '';
    const label = ROLE_LABELS[role] ?? role;
    return role === 'admin'
      ? 'Full access — all decision tools available'
      : `Tools available for ${label}`;
  });

  readonly modelInfo: Record<string, { title: string; goal: string; fields: { name: string; desc: string }[]; benchmarks?: { name: string; desc: string; example: string }[] }> = {
    price: {
      title: 'Smart Event Pricing',
      goal: 'This tool estimates the best price for your event. Think of it as a smart pricing advisor — you enter the event details and it tells you what price to expect.',
      fields: [
        { name: 'Price', desc: 'The base price you plan to charge.' },
        { name: 'Budget', desc: 'Total budget for the event.' },
        { name: 'Marketing Spend', desc: 'How much you spent on promotion.' },
        { name: 'New Beneficiaries', desc: 'Number of new attendees expected.' },
        { name: 'Reservations', desc: 'How many bookings already made.' },
        { name: 'Nb Events', desc: 'How many events you have run before.' },
        { name: 'Avg Spent / User', desc: 'Average amount each attendee spends.' },
        { name: 'Type', desc: 'The kind of event (Corporate, Wedding, Party…).' },
        { name: 'Status', desc: 'Whether the event is confirmed, pending, or cancelled.' },
      ]
    },
    fidel: {
      title: 'Client Return Likelihood',
      goal: 'This tool predicts whether a client will come back and book again. It gives you a loyalty score and tells you what action to take — like sending a personalised offer or a newsletter.',
      fields: [
        { name: 'Price / Budget / Final Price', desc: 'The financial details of the event.' },
        { name: 'Rating', desc: 'How the client rated the event (0 to 5).' },
        { name: 'Visitors', desc: 'How many people attended.' },
        { name: 'Marketing Spend', desc: 'Budget spent on promotion.' },
        { name: 'Has Complaint', desc: 'Did the client file a complaint? Yes or No.' },
        { name: 'Event Type', desc: 'Type of event (Corporate, Wedding, Party…).' },
        { name: 'Season', desc: 'Which season the event took place in.' },
        { name: 'Is Weekend', desc: 'Was the event on a weekend?' },
        { name: 'Month', desc: 'Which month the event happened.' },
      ],
      benchmarks: [
        { name: 'Correct Predictions', desc: 'Out of every 100 clients assessed, how many the tool correctly identified as loyal or not loyal.', example: '85% means 85 out of 100 predictions were correct.' },
        { name: 'Loyal Clients Found', desc: 'Out of all truly loyal clients, how many the tool successfully spotted. A high score means fewer loyal clients are missed.', example: '78% means the tool caught 78 out of every 100 genuinely loyal clients.' },
        { name: 'Prediction Confidence', desc: 'How reliable the assessment is. Ranges from 50% (random) to 100% (perfect). Higher means you can trust the result more.', example: '91% means the tool almost always correctly ranks a loyal client above a non-loyal one.' },
      ]
    },
    loyalty: {
      title: 'Client Loyalty Check',
      goal: 'A quick answer: will this client be loyal? It gives a simple Yes/No result with a confidence percentage.',
      fields: [
        { name: 'Price / Budget / Final Price', desc: 'The financial details of the event.' },
        { name: 'Rating', desc: 'Client satisfaction score (0 to 5).' },
        { name: 'Visitors', desc: 'Number of attendees.' },
        { name: 'Event Date', desc: 'When the event took place.' },
        { name: 'Event Type', desc: 'The category of the event.' },
      ]
    },
    cluster: {
      title: 'Event Profile Grouping',
      goal: 'This tool groups your events into categories based on their profile. It helps you understand what kind of event you are dealing with — Premium, Potential, or At-Risk — so you can manage each type differently.',
      fields: [
        { name: 'Budget / Price / Final Price', desc: 'The financial profile of the event.' },
        { name: 'Rating', desc: 'Client satisfaction score.' },
        { name: 'Visitors', desc: 'Number of attendees.' },
        { name: 'Algorithm', desc: 'Method used to group events. Standard groups into fixed categories; Flexible finds natural groupings automatically.' },
        { name: 'Event Type', desc: 'The category of the event.' },
        { name: 'Reservation Status', desc: 'Whether the booking is confirmed, pending, or cancelled.' },
      ],
      benchmarks: [
        { name: 'Group Clarity', desc: 'How well-defined each group is. Closer to 1 means the groups are clean and meaningful.', example: '0.62 means events in the same group are clearly similar to each other.' },
        { name: 'Group Separation', desc: 'How distinct the groups are. Lower is better — it means groups are well separated.', example: '0.85 is a good score; 2.5 would mean groups overlap too much.' },
        { name: 'Groups Found', desc: 'The number of distinct event profiles discovered in your data.', example: '3 groups might represent Premium, Standard, and At-Risk events.' },
        { name: 'Unclassified', desc: 'Events that did not fit clearly into any group — unusual cases worth reviewing.', example: '5 unclassified events means 5 events were too unusual to place in any group.' },
      ]
    },
    forecast: {
      title: 'Booking Demand Forecast',
      goal: 'This tool looks at past booking history and predicts how many reservations to expect in the coming months. Like a weather forecast, but for your event demand.',
      fields: [
        { name: 'Category', desc: 'The type of events to forecast (e.g. Concerts, Weddings…).' },
        { name: 'Horizon', desc: 'How many months ahead you want to look.' },
      ],
      benchmarks: [
        { name: 'Avg. Error Rate', desc: 'On average, how far off the forecast is. Lower is better — 0% would be perfect.', example: '12% means the forecast is typically off by about 12 bookings for every 100 expected.' },
        { name: 'Typical Miss', desc: 'The usual difference between forecast and actual bookings each month.', example: 'A Typical Miss of 8 means the forecast is usually off by about 8 bookings per month.' },
        { name: 'Worst-Case Miss', desc: 'Gives more weight to months with the biggest forecast errors. Useful for spotting occasional surprises.', example: 'If Typical Miss is 8 but Worst-Case Miss is 20, a few months had much larger errors worth investigating.' },
      ]
    },
    sentiment: {
      title: 'Client Feedback Tone',
      goal: 'Paste any client review or comment and this tool instantly tells you if it is Positive, Negative, or Neutral. No reading required — it reads it for you.',
      fields: [
        { name: 'Review Text', desc: 'Any written feedback from a client, in any language.' },
      ]
    },
    reco: {
      title: 'Personalised Event Suggestions',
      goal: 'Given a client ID, this tool suggests events they are most likely to enjoy based on what similar clients have attended. Like a "You might also like…" feature.',
      fields: [
        { name: 'Beneficiary ID', desc: 'The unique ID of the client in your system.' },
        { name: 'Count', desc: 'How many suggestions you want (1 to 10).' },
      ]
    },
    anomaly: {
      title: 'Unusual Activity Alert',
      goal: 'This tool scans all your event financial data and flags anything unusual — events with abnormal prices, budgets, or visitor numbers. Think of it as a fraud or error detector.',
      fields: [
        { name: '(No inputs needed)', desc: 'The tool automatically analyses all events in the database.' },
      ]
    },
    revenue: {
      title: 'Revenue Outlook',
      goal: 'Think of this as a financial weather forecast for your business. By studying how your revenue has behaved over recent months, the system projects what your income is likely to look like over the coming months. No input needed — it runs automatically.',
      fields: [
        { name: 'No input required', desc: 'The forecast is computed automatically from your revenue history. Just open the panel and the chart loads instantly.' },
        { name: 'Projected Revenue', desc: 'The estimated income for each upcoming month, shown as a bar chart so you can spot growth or slowdowns at a glance.' },
        { name: 'Monthly Trend', desc: 'The shape of the bars tells the story — rising bars mean growth, flat or falling bars signal a slower period ahead.' },
      ]
    },
    dl: {
      title: 'Advanced Loyalty Predictor',
      goal: 'A more powerful version of the Client Return Likelihood tool. It uses advanced analysis to detect more complex patterns. Enter the same details and get a second opinion.',
      fields: [
        { name: '(Same inputs as Client Return Likelihood)', desc: 'Fill the Client Return Likelihood form first, then use this tool for a second opinion.' },
      ],
      benchmarks: [
        { name: 'Correct Predictions', desc: 'Out of every 100 clients assessed, how many the tool correctly identified as loyal or not loyal.', example: '88% means 88 out of 100 predictions were correct.' },
        { name: 'Balanced Score', desc: 'A combined measure of precision and thoroughness. Closer to 100% is better.', example: '84% means the tool is both precise and thorough in identifying loyal clients.' },
        { name: 'Prediction Confidence', desc: 'How reliable the assessment is. 50% is random; 100% is perfect.', example: '93% means the tool almost always correctly identifies a truly loyal client.' },
        { name: 'Training Rounds', desc: 'How many improvement cycles the tool completed before reaching its best performance.', example: '47 rounds means the tool optimised itself 47 times before finishing.' },
      ]
    },
  };

  openModelInfo(key: string, event: MouseEvent): void {
    event.stopPropagation();
    this.modelInfoKey.set(key);
    this.modelInfoVisible.set(true);
  }

  // ── Price Prediction ──────────────────────────────────────────────────────
  priceForm: PricePredictRequest = {
    price: 500, budget: 2000, marketing_spend: 300,
    new_beneficiaries: 50, reservations: 80, nb_events: 5,
    avg_spent_user: 120, type: 'Corporate Event', status: 'confirmed'
  };
  priceResult  = signal<PricePredictResponse | null>(null);
  priceLoading = signal(false);
  priceError   = signal<string | null>(null);

  // ── Fidelisation Prediction ───────────────────────────────────────────────
  fidelForm: FidelisationRequest = {
    price: 500, budget: 2000, final_price: 480, rating: 4.2,
    visitors: 120, marketing_spend: 300, price_budget_ratio: 0.25,
    margin: -20, has_complaint: 0, type_encoded: 0,
    season_encoded: 2, is_weekend: 0, month: 6
  };
  fidelResult  = signal<FidelisationResponse | null>(null);
  fidelLoading = signal(false);
  fidelError   = signal<string | null>(null);

  // ── Loyalty Prediction ────────────────────────────────────────────────────
  loyaltyForm: LoyaltyRequest = {
    price: 500, budget: 2000, final_price: 480, rating: 4.2,
    visitors: 120, event_date: new Date().toISOString().split('T')[0],
    event_type: 'Corporate Event', id_complaint: null
  };
  loyaltyResult  = signal<LoyaltyResponse | null>(null);
  loyaltyLoading = signal(false);
  loyaltyError   = signal<string | null>(null);

  // ── Cluster Prediction ────────────────────────────────────────────────────
  clusterForm: ClusterRequest = {
    budget: 2000, price: 500, final_price: 480, rating: 4.2,
    visitors: 120, complaint_status: 'closed', complaint_subject: 'Autre',
    event_type: 'Corporate Event', reservation_status: 'confirmed', algo: 'kmeans'
  };
  clusterResult  = signal<ClusterResponse | null>(null);
  clusterLoading = signal(false);
  clusterError   = signal<string | null>(null);

  // ── Forecasting ──────────────────────────────────────────────────────────
  forecastForm: ForecastRequest = { category_name: '', horizon: 6 };
  forecastResult = signal<ForecastResponse | null>(null);
  forecastLoading = signal(false);
  forecastError = signal<string | null>(null);
  revenueForecast = signal<{date: string; value: number}[] | null>(null);
  revenueHistory  = signal<{date: string; value: number}[] | null>(null);
  revenueModel    = signal<string | null>(null);
  revenueLoading = signal(false);
  revenueError = signal<string | null>(null);
  revenueHorizon = signal<4 | 6 | 12>(6);
  categories = signal<string[]>([]);

  // ── NEW: Sentiment ────────────────────────────────────────────────────────
  sentimentText = 'The event was absolutely fantastic!';
  sentimentResult = signal<SentimentResponse | null>(null);
  sentimentLoading = signal(false);

  // ── NEW: Recommendation ───────────────────────────────────────────────────
  recoBeneId = 1;
  recoCount = 5;
  recoResult = signal<RecommendationResponse | null>(null);
  recoLoading = signal(false);
  recoError = signal<string | null>(null);

  // ── NEW: Anomalies ────────────────────────────────────────────────────────
  anomalyResult = signal<AnomalyResponse | null>(null);
  anomalyLoading = signal(false);
  anomalyError = signal<string | null>(null);

  // ── NEW: Deep Learning (MLP) ──────────────────────────────────────────────
  dlResult = signal<DeepLearningResponse | null>(null);
  dlLoading = signal(false);
  dlError = signal<string | null>(null);

  private onHashChange = () => this.readHash();

  ngOnInit(): void {
    this.readHash();
    window.addEventListener('hashchange', this.onHashChange);
    this.loadCategories();
  }

  private loadCategories(): void {
    this.api.getCategories().subscribe({
      next: (cats) => {
        this.categories.set(cats);
        if (cats.length > 0) this.forecastForm.category_name = cats[0];
      }
    });
  }

  ngAfterViewInit(): void {
    this.animateSection(this.activeSection());
  }

  ngOnDestroy(): void {
    window.removeEventListener('hashchange', this.onHashChange);
  }

  private readHash(): void {
    const hash = (window.location.hash.replace('#', '') || 'overview') as Section;
    if (PROTECTED.includes(hash) && !this.auth.isLoggedIn()) {
      this.activeSection.set('overview');
      window.location.hash = 'overview';
    } else {
      this.selectedModel.set(null);
      this.activeSection.set(hash);
      setTimeout(() => this.animateSection(hash), 50);
    }
  }

  private animateSection(section: Section): void {
    if (typeof window === 'undefined') return;
    const gsap = (window as any).gsap;
    if (!gsap) return;
    if (section === 'overview') {
      gsap.from('.hero > *', { opacity: 0, y: 24, stagger: 0.1, duration: 0.55, ease: 'power2.out', clearProps: 'all' });
      gsap.from('.stat-card', { opacity: 0, y: 20, stagger: 0.08, duration: 0.5, ease: 'power2.out', delay: 0.3, clearProps: 'all' });
    } else if (section === 'about') {
      gsap.from('.feature-card', { opacity: 0, y: 24, stagger: 0.08, duration: 0.5, ease: 'power2.out', clearProps: 'all' });
    } else if (section === 'lab') {
      this.animateLabCards();
    }
  }

  private animateLabCards(): void {
    if (typeof window === 'undefined') return;
    const gsap = (window as any).gsap;
    if (!gsap) return;
    gsap.from('.catalog-card', {
      opacity: 0, y: 28, scale: 0.97,
      stagger: 0.07, duration: 0.5,
      ease: 'power2.out', clearProps: 'all'
    });
  }

  selectModel(id: string | null): void {
    if (typeof window === 'undefined') return;
    const gsap = (window as any).gsap;
    this.selectedModel.set(id);
    if (id === 'revenue') {
      this.runRevenueForecast();
    }
    if (id && gsap) {
      setTimeout(() => {
        gsap.from('.catalog-panel', {
          opacity: 0, y: 16, duration: 0.35, ease: 'power2.out'
        });
        document.querySelector('.catalog-panel')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 0);
    }
  }

  navigate(section: string): void {
    window.location.hash = section;
  }

  isProtectedAndLocked(section: Section): boolean {
    return PROTECTED.includes(section) && !this.auth.isLoggedIn();
  }

  get forecastTotalReservations(): number {
    return this.forecastResult()?.forecast.reduce((sum, p) => sum + p.value, 0) ?? 0;
  }

  get forecastSeries(): Array<{ label: string; value: number; phase: 'history' | 'forecast' }> {
    const result = this.forecastResult();
    if (!result) return [];
    const history = (result.history ?? []).map((item) => ({
      label: item.date,
      value: item.value,
      phase: 'history' as const
    }));
    const forecast = result.forecast.map((item) => ({
      label: item.date,
      value: item.value,
      phase: 'forecast' as const
    }));
    return [...history, ...forecast];
  }

  get forecastMaxValue(): number {
    const values = this.forecastSeries.map((item) => item.value);
    return values.length ? Math.max(...values, 1) : 1;
  }

  get forecastPolylinePoints(): string {
    const series = this.forecastSeries;
    if (!series.length) return '';
    return series
      .map((item, index) => {
        const x = series.length === 1 ? 0 : (index / (series.length - 1)) * 100;
        const y = 100 - (item.value / this.forecastMaxValue) * 100;
        return `${x},${y}`;
      })
      .join(' ');
  }

  get forecastDividerX(): number | null {
    const historyLength = this.forecastResult()?.history?.length ?? 0;
    const total = this.forecastSeries.length;
    if (!historyLength || historyLength >= total) return null;
    return ((historyLength - 1) / (total - 1)) * 100;
  }

  get revenueForecastData(): ForecastResponse | null {
    const forecast = this.revenueForecast();
    if (!forecast) return null;
    return {
      status: 'success',
      model: this.revenueModel() ?? undefined,
      forecast,
      history: this.revenueHistory() ?? []
    };
  }

  shortNumber(v: number): string {
    if (v >= 1_000_000) return (v / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (v >= 1_000) return (v / 1_000).toFixed(1).replace(/\.0$/, '') + 'K';
    return v.toFixed(0);
  }

  get revenueNextMonth(): number {
    return this.revenueForecast()?.[0]?.value ?? 0;
  }
  get revenueMonthlyAvg(): number {
    const f = this.revenueForecast();
    if (!f?.length) return 0;
    return f.reduce((s, p) => s + p.value, 0) / f.length;
  }
  get revenueTotal(): number {
    return this.revenueForecast()?.reduce((s, p) => s + p.value, 0) ?? 0;
  }
  get revenueMax(): number {
    const f = this.revenueForecast();
    if (!f?.length) return 1;
    return Math.max(...f.map(p => p.value), 1);
  }
  revenueBarHeight(value: number): number {
    return (value / this.revenueMax) * 100;
  }

  get anomalyRatePercent(): number | null {
    const result = this.anomalyResult();
    if (!result || !result.total_count) return null;
    return (result.anomaly_count / result.total_count) * 100;
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  runPricePredict(): void {
    this.priceLoading.set(true);
    this.priceResult.set(null);
    this.priceError.set(null);
    this.api.predictPrice(this.priceForm).subscribe({
      next: (res) => { this.priceResult.set(res); this.priceLoading.set(false); this.animateResult('.price-result'); },
      error: (e)  => { this.priceError.set(e?.error?.detail ?? 'API unreachable.'); this.priceLoading.set(false); }
    });
  }

  trainPrice(): void {
    this.priceLoading.set(true);
    this.priceError.set(null);
    this.api.trainPrice().subscribe({
      next: () => {
        this.priceLoading.set(false);
        alert('Price model trained successfully!');
      },
      error: (e) => {
        this.priceError.set(e?.error?.detail?.message ?? 'Training failed.');
        this.priceLoading.set(false);
      }
    });
  }

  runFidelPredict(): void {
    this.fidelLoading.set(true);
    this.fidelResult.set(null);
    this.fidelError.set(null);
    this.api.predictFidelisation(this.fidelForm).subscribe({
      next: (res) => { this.fidelResult.set(res); this.fidelLoading.set(false); this.animateResult('.fidel-result'); },
      error: (e)  => { this.fidelError.set(e?.error?.detail ?? 'API unreachable.'); this.fidelLoading.set(false); }
    });
  }

  trainFidel(): void {
    this.fidelLoading.set(true);
    this.fidelError.set(null);
    this.api.trainFidelisation().subscribe({
      next: () => { 
        this.fidelLoading.set(false); 
        alert('Model trained successfully! You can now run predictions.');
      },
      error: (e) => { 
        this.fidelError.set(e?.error?.detail?.message ?? 'Training failed. Check database connection.'); 
        this.fidelLoading.set(false); 
      }
    });
  }


  runLoyaltyPredict(): void {
    this.loyaltyLoading.set(true);
    this.loyaltyResult.set(null);
    this.loyaltyError.set(null);
    this.api.predictLoyalty(this.loyaltyForm).subscribe({
      next: (res) => { this.loyaltyResult.set(res); this.loyaltyLoading.set(false); this.animateResult('.loyalty-result'); },
      error: (e)  => { this.loyaltyError.set(e?.error?.detail ?? e?.error?.error ?? 'API unreachable.'); this.loyaltyLoading.set(false); }
    });
  }

  runClusterPredict(): void {
    this.clusterLoading.set(true);
    this.clusterResult.set(null);
    this.clusterError.set(null);
    this.api.predictCluster(this.clusterForm).subscribe({
      next: (res) => { this.clusterResult.set(res); this.clusterLoading.set(false); this.animateResult('.cluster-result'); },
      error: (e)  => { this.clusterError.set(e?.error?.detail ?? e?.error?.error ?? 'API unreachable.'); this.clusterLoading.set(false); }
    });
  }

  runRevenueForecast(): void {
    this.revenueLoading.set(true);
    this.revenueForecast.set(null);
    this.revenueHistory.set(null);
    this.revenueModel.set(null);
    this.revenueError.set(null);
    this.api.getRevenueForecast(this.revenueHorizon()).subscribe({
      next: (res) => {
        this.revenueForecast.set(res.forecast);
        this.revenueHistory.set(res.history ?? []);
        this.revenueModel.set(res.model ?? null);
        this.revenueLoading.set(false);
      },
      error: (e) => { this.revenueError.set(e?.error?.detail ?? "Revenue forecast unavailable."); this.revenueLoading.set(false); }
    });
  }

  runForecast(): void {
    this.forecastLoading.set(true);
    this.forecastResult.set(null);
    this.forecastError.set(null);
    this.api.forecast(this.forecastForm).subscribe({
      next: (res) => { 
        this.forecastResult.set(res); 
        this.forecastLoading.set(false); 
        this.animateResult('.forecast-result'); 
      },
      error: (e) => { 
        this.forecastError.set(e?.error?.detail ?? 'Forecast failed.'); 
        this.forecastLoading.set(false); 
      }
    });
  }

  runSentiment(): void {
    this.sentimentLoading.set(true);
    this.sentimentResult.set(null);
    this.api.predictSentiment(this.sentimentText).subscribe({
      next: (res) => {
        this.sentimentResult.set(res);
        this.sentimentLoading.set(false);
        this.animateResult('.sentiment-result');
      },
      error: () => this.sentimentLoading.set(false)
    });
  }

  runReco(): void {
    this.recoLoading.set(true);
    this.recoResult.set(null);
    this.recoError.set(null);
    this.api.recommendEvents(this.recoBeneId, this.recoCount).subscribe({
      next: (res) => {
        this.recoResult.set(res);
        this.recoLoading.set(false);
        this.animateResult('.reco-result');
      },
      error: (e) => {
        this.recoError.set(e?.error?.detail ?? 'Recommendation request failed.');
        this.recoLoading.set(false);
      }
    });
  }

  runAnomalies(): void {
    this.anomalyLoading.set(true);
    this.anomalyResult.set(null);
    this.anomalyError.set(null);
    this.api.detectAnomalies().subscribe({
      next: (res) => {
        this.anomalyResult.set(res);
        this.anomalyLoading.set(false);
        this.animateResult('.anomaly-result');
      },
      error: (e) => {
        this.anomalyError.set(e?.error?.detail ?? 'Anomaly detection failed.');
        this.anomalyLoading.set(false);
      }
    });
  }

  runDL(): void {
    this.dlLoading.set(true);
    this.dlResult.set(null);
    this.dlError.set(null);
    this.api.predictDeepLearning(this.fidelForm).subscribe({
      next: (res) => {
        this.dlResult.set(res);
        this.dlLoading.set(false);
        this.animateResult('.dl-result');
      },
      error: (e) => {
        this.dlError.set(e?.error?.detail ?? 'Deep learning prediction failed.');
        this.dlLoading.set(false);
      }
    });
  }

  private animateResult(selector: string): void {
    if (typeof window === 'undefined') return;
    const gsap = (window as any).gsap;
    if (!gsap) return;
    setTimeout(() => {
      gsap.from(selector, { opacity: 0, y: 10, duration: 0.4, ease: 'power2.out' });
    }, 0);
  }
}
