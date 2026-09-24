import './react-global';
import '@design-system/components/bundle.css';
import '@design-system/components/bundle.js';
import type * as QuantForge from '@design-system/components/index';
import { installTokens } from './tokens';

export type * from '@design-system/components/index';

installTokens();

/** The QuantForge components; they only format numbers the API returns. */
export const QF: typeof QuantForge = window.QuantForge;
