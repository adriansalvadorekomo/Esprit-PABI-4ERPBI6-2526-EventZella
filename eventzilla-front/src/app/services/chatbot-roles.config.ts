export interface ChatbotRoleConfig {
  title: string;
  allowedTopics: string[];
  quickSuggestions: string[];
}

export const CHATBOT_ROLES: Record<string, ChatbotRoleConfig> = {
  marketing: {
    title: 'Marketing AI Assistant',
    allowedTopics: [
      'customer loyalty', 'client feedback', 'personalized event', 'customer segmentation',
      'campaign', 'visitor engagement', 'marketing kpi', 'retention', 'satisfaction',
      'engagement', 'recommendation', 'sentiment', 'channel', 'beneficiar',
    ],
    quickSuggestions: [
      'Show customer engagement trends',
      'Analyze client feedback sentiment',
      'Top performing event categories',
      'Personalized event recommendations',
      'Customer retention analysis',
    ],
  },
  quality: {
    title: 'Quality AI Assistant',
    allowedTopics: [
      'client satisfaction', 'service quality', 'return likelihood', 'feedback',
      'unusual activity', 'complaint', 'quality kpi', 'rating', 'review',
      'negative', 'provider quality', 'satisfaction trend',
    ],
    quickSuggestions: [
      'Average client rating',
      'Providers with lowest ratings',
      'Negative feedback analysis',
      'Satisfaction trend',
      'Quality KPI dashboard',
    ],
  },
  operational: {
    title: 'Operational AI Assistant',
    allowedTopics: [
      'booking demand', 'event profile', 'operational', 'planning', 'traffic',
      'unusual activity', 'reservation', 'anomaly', 'forecast', 'season',
      'busiest', 'visitor flow', 'overload', 'peak',
    ],
    quickSuggestions: [
      'Booking demand forecast',
      'Reservation trends',
      'Visitor flow prediction',
      'Operational KPI analysis',
      'Detect anomalies',
    ],
  },
  business: {
    title: 'Business AI Assistant',
    allowedTopics: [
      'pricing', 'revenue', 'profitability', 'business kpi', 'strategic',
      'financial', 'provider performance', 'profit', 'income', 'earnings',
      'cost', 'budget', 'price', 'quarter', 'forecast revenue',
    ],
    quickSuggestions: [
      'Total revenue',
      'Revenue forecast',
      'Profitability analysis',
      'Top business KPIs',
      'Pricing optimization',
    ],
  },
  admin: {
    title: 'Admin AI Assistant',
    allowedTopics: ['*'],
    quickSuggestions: [
      'Show events by season',
      'Top 5 providers by reservations',
      'Show reservations by status',
      'What is the average rating?',
      'Which event category has the most events?',
      'Show visitor trend by month',
      'What is the total revenue?',
      'Which providers have the lowest ratings?',
    ],
  },
};
