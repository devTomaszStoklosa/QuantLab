// The design system bundle is a script that reads React from `window` when it runs
// (presentation/design-system). This module is imported before it, so the bundle and
// the app render with one and the same React.
import React from 'react';

declare global {
  interface Window {
    React: typeof React;
  }
}

window.React = React;
