import type ro from './ro'

// Typed against the Romanian resources, so a missing or extra key fails the
// type check.
const en: typeof ro = {
  app: {
    name: 'SentinelCore',
    loading: 'Loading…',
  },
  scope: {
    label: 'Perspective',
    personal: 'My account',
    organization: 'Organization',
  },
  nav: {
    label: 'Main navigation',
    overview: 'Overview',
    mySessions: 'My sessions',
    myActivity: 'My activity',
    securityEvents: 'Security events',
    auditLog: 'Audit log',
    users: 'Users',
  },
  roles: {
    user: 'User',
    admin: 'Administrator',
    security_analyst: 'Security analyst',
    owner: 'Owner',
  },
  account: {
    menu: 'Account menu',
    theme: 'Theme',
    themeDark: 'Dark',
    themeLight: 'Light',
    themeSystem: 'System',
    language: 'Language',
    logout: 'Log out',
  },
  login: {
    title: 'Sign in',
    subtitle: 'Monitor the activity of your accounts.',
    email: 'Email',
    password: 'Password',
    submit: 'Sign in',
    submitting: 'Checking…',
    errors: {
      invalid: 'Wrong email or password.',
      inactive: 'This account is deactivated. Contact an administrator.',
      locked_one: 'Too many failed attempts. Try again in {{count}} minute.',
      locked_few: 'Too many failed attempts. Try again in {{count}} minutes.',
      locked_other: 'Too many failed attempts. Try again in {{count}} minutes.',
      validation: 'Check the email address and password.',
      network: 'The server is not responding. Check your connection and try again.',
    },
  },
  overview: {
    greeting: 'Welcome, {{name}}',
    profile: 'Profile',
    username: 'Username',
    email: 'Email',
    role: 'Role',
    memberSince: 'Member since',
    status: 'Status',
    active: 'Active',
  },
  orgOverview: {
    title: 'Organization',
    subtitle: 'Activity across all accounts.',
  },
  placeholder: {
    title: 'In progress',
    body: 'This section arrives in a later stage of the project.',
  },
  errors: {
    forbiddenTitle: 'Restricted',
    forbiddenBody: 'The organization perspective is available to administrators and security analysts.',
    backToAccount: 'Back to my account',
    notFoundTitle: 'Page not found',
    notFoundBody: 'This address does not match any page in the app.',
    loadFailedTitle: 'The data did not load',
    loadFailedBody: 'The server did not respond. Check your connection and try again.',
    retry: 'Try again',
  },
}

export default en
