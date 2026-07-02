if (import.meta.env.VITE_APP_TARGET === 'dev-console') {
  void import('./dev-main')
} else {
  void import('./learner-main')
}
