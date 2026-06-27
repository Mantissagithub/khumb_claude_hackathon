// Assembles the per-locale dictionaries (one file each under ./locales) into a
// single { code: dict } map. en.js is the reference; all others mirror its keys.
import en from "./locales/en";
import hi from "./locales/hi";
import mr from "./locales/mr";
import bn from "./locales/bn";
import te from "./locales/te";
import ta from "./locales/ta";
import gu from "./locales/gu";
import kn from "./locales/kn";
import ml from "./locales/ml";
import pa from "./locales/pa";
import or from "./locales/or";
import as from "./locales/as";
import ur from "./locales/ur";
import sa from "./locales/sa";
import ks from "./locales/ks";

export const translations = { en, hi, mr, bn, te, ta, gu, kn, ml, pa, or, as, ur, sa, ks };

export { LANGS, SPEECH_LOCALE } from "./languages";
