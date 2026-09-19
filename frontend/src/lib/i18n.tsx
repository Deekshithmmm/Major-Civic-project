/**
 * Minimal i18n: English, Hindi, and one regional language (Kannada), selectable without an
 * account (spec 2.6, "Accessibility and language"). Deliberately a small hand-rolled context
 * rather than a full i18n library - the string set is small and the bundle stays light for
 * low-end phones on 3G.
 *
 * The Hindi and Kannada strings here are a working first pass and should be reviewed by fluent
 * speakers before any real deployment.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

export type Lang = 'en' | 'hi' | 'kn'

export const LANGUAGES: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'हिन्दी' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
]

const STRINGS = {
  appName: {
    en: 'Civic Accountability',
    hi: 'नागरिक जवाबदेही',
    kn: 'ನಾಗರಿಕ ಹೊಣೆಗಾರಿಕೆ',
  },
  navReport: { en: 'Report an issue', hi: 'शिकायत दर्ज करें', kn: 'ದೂರು ದಾಖಲಿಸಿ' },
  navBoard: { en: 'Status board', hi: 'स्थिति बोर्ड', kn: 'ಸ್ಥಿತಿ ಫಲಕ' },
  navTrack: { en: 'Track a report', hi: 'शिकायत ट्रैक करें', kn: 'ದೂರು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ' },
  navOfficer: { en: 'Officer login', hi: 'अधिकारी लॉगिन', kn: 'ಅಧಿಕಾರಿ ಲಾಗಿನ್' },
  language: { en: 'Language', hi: 'भाषा', kn: 'ಭಾಷೆ' },

  reportTitle: { en: 'Report a civic infrastructure issue', hi: 'नागरिक अवसंरचना समस्या दर्ज करें', kn: 'ನಾಗರಿಕ ಮೂಲಸೌಕರ್ಯ ಸಮಸ್ಯೆ ದಾಖಲಿಸಿ' },
  reportAnonymous: {
    en: 'No account needed. Your report is anonymous by default.',
    hi: 'खाते की आवश्यकता नहीं। आपकी शिकायत डिफ़ॉल्ट रूप से गुमनाम है।',
    kn: 'ಖಾತೆ ಅಗತ್ಯವಿಲ್ಲ. ನಿಮ್ಮ ದೂರು ಪೂರ್ವನಿಯೋಜಿತವಾಗಿ ಅನಾಮಧೇಯವಾಗಿದೆ.',
  },
  category: { en: 'Category', hi: 'श्रेणी', kn: 'ವರ್ಗ' },
  description: { en: 'Description (optional)', hi: 'विवरण (वैकल्पिक)', kn: 'ವಿವರಣೆ (ಐಚ್ಛಿಕ)' },
  photo: { en: 'Photo or video', hi: 'फ़ोटो या वीडियो', kn: 'ಫೋಟೋ ಅಥವಾ ವೀಡಿಯೊ' },
  photoHelp: {
    en: 'Faces are blurred and location metadata is stripped before your file is stored.',
    hi: 'आपकी फ़ाइल संग्रहीत होने से पहले चेहरे धुंधले किए जाते हैं और स्थान मेटाडेटा हटाया जाता है।',
    kn: 'ನಿಮ್ಮ ಫೈಲ್ ಸಂಗ್ರಹಿಸುವ ಮೊದಲು ಮುಖಗಳನ್ನು ಮಸುಕುಗೊಳಿಸಲಾಗುತ್ತದೆ ಮತ್ತು ಸ್ಥಳ ಮೆಟಾಡೇಟಾ ತೆಗೆದುಹಾಕಲಾಗುತ್ತದೆ.',
  },
  location: { en: 'Location', hi: 'स्थान', kn: 'ಸ್ಥಳ' },
  locationHelp: {
    en: 'Tap the map to drop a pin where the problem is.',
    hi: 'समस्या कहाँ है, वहाँ पिन लगाने के लिए मानचित्र पर टैप करें।',
    kn: 'ಸಮಸ್ಯೆ ಇರುವ ಸ್ಥಳದಲ್ಲಿ ಪಿನ್ ಇರಿಸಲು ನಕ್ಷೆಯನ್ನು ಟ್ಯಾಪ್ ಮಾಡಿ.',
  },
  phoneOptional: { en: 'Phone number (optional)', hi: 'फ़ोन नंबर (वैकल्पिक)', kn: 'ಫೋನ್ ಸಂಖ್ಯೆ (ಐಚ್ಛಿಕ)' },
  phoneHelp: {
    en: 'Only used to send you status updates. Stored separately and deleted when the issue is resolved.',
    hi: 'केवल स्थिति अपडेट भेजने के लिए उपयोग किया जाता है। अलग से संग्रहीत और समस्या हल होने पर हटा दिया जाता है।',
    kn: 'ಸ್ಥಿತಿ ನವೀಕರಣಗಳನ್ನು ಕಳುಹಿಸಲು ಮಾತ್ರ ಬಳಸಲಾಗುತ್ತದೆ. ಪ್ರತ್ಯೇಕವಾಗಿ ಸಂಗ್ರಹಿಸಿ ಸಮಸ್ಯೆ ಪರಿಹಾರವಾದಾಗ ಅಳಿಸಲಾಗುತ್ತದೆ.',
  },
  submit: { en: 'Submit report', hi: 'शिकायत भेजें', kn: 'ದೂರು ಸಲ್ಲಿಸಿ' },
  submitting: { en: 'Submitting…', hi: 'भेजा जा रहा है…', kn: 'ಸಲ್ಲಿಸಲಾಗುತ್ತಿದೆ…' },
  processing: { en: 'Processing…', hi: 'प्रोसेस किया जा रहा है…', kn: 'ಪ್ರಕ್ರಿಯೆಗೊಳಿಸಲಾಗುತ್ತಿದೆ…' },
  processingHelp: {
    en: 'Uploaded. Faces are being blurred and location data removed — videos can take a few minutes. Keep this page open.',
    hi: 'अपलोड हो गया। चेहरे धुंधले किए जा रहे हैं और स्थान डेटा हटाया जा रहा है — वीडियो में कुछ मिनट लग सकते हैं। यह पेज खुला रखें।',
    kn: 'ಅಪ್‌ಲೋಡ್ ಆಗಿದೆ. ಮುಖಗಳನ್ನು ಮಸುಕುಗೊಳಿಸಲಾಗುತ್ತಿದೆ ಮತ್ತು ಸ್ಥಳ ಡೇಟಾ ತೆಗೆದುಹಾಕಲಾಗುತ್ತಿದೆ — ವೀಡಿಯೊಗಳಿಗೆ ಕೆಲವು ನಿಮಿಷಗಳು ಬೇಕಾಗಬಹುದು. ಈ ಪುಟವನ್ನು ತೆರೆದಿಡಿ.',
  },
  errorTimeout: {
    en: 'Your file uploaded, but the server stopped responding. Please try again — a repeat report from the same spot is merged with the first, not duplicated.',
    hi: 'आपकी फ़ाइल अपलोड हो गई, लेकिन सर्वर ने जवाब देना बंद कर दिया। कृपया पुनः प्रयास करें — उसी स्थान से दोबारा की गई शिकायत पहली शिकायत में जोड़ दी जाती है, दोहराई नहीं जाती।',
    kn: 'ನಿಮ್ಮ ಫೈಲ್ ಅಪ್‌ಲೋಡ್ ಆಗಿದೆ, ಆದರೆ ಸರ್ವರ್ ಪ್ರತಿಕ್ರಿಯಿಸುವುದನ್ನು ನಿಲ್ಲಿಸಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ — ಅದೇ ಸ್ಥಳದಿಂದ ಮತ್ತೆ ಮಾಡಿದ ದೂರನ್ನು ಮೊದಲನೆಯದರೊಂದಿಗೆ ಸೇರಿಸಲಾಗುತ್ತದೆ, ನಕಲು ಮಾಡಲಾಗುವುದಿಲ್ಲ.',
  },
  errorNetwork: {
    en: "Couldn't reach the server. Check your connection and try again.",
    hi: 'सर्वर से संपर्क नहीं हो सका। अपना कनेक्शन जांचें और पुनः प्रयास करें।',
    kn: 'ಸರ್ವರ್ ತಲುಪಲು ಸಾಧ್ಯವಾಗಲಿಲ್ಲ. ನಿಮ್ಮ ಸಂಪರ್ಕ ಪರಿಶೀಲಿಸಿ ಮತ್ತು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  },
  submitted: { en: 'Report received', hi: 'शिकायत प्राप्त हुई', kn: 'ದೂರು ಸ್ವೀಕರಿಸಲಾಗಿದೆ' },
  trackingToken: { en: 'Your tracking code', hi: 'आपका ट्रैकिंग कोड', kn: 'ನಿಮ್ಮ ಟ್ರ್ಯಾಕಿಂಗ್ ಕೋಡ್' },
  // Neutral wording: on the public board the report belongs to someone else, so "your" is wrong.
  trackingCodeLabel: { en: 'Tracking code', hi: 'ट्रैकिंग कोड', kn: 'ಟ್ರ್ಯಾಕಿಂಗ್ ಕೋಡ್' },
  trackingHelp: {
    en: 'Save this code. It is the only way to check your report later, and it is linked to no identity.',
    hi: 'यह कोड सहेजें। बाद में अपनी शिकायत देखने का यही एकमात्र तरीका है, और यह किसी पहचान से जुड़ा नहीं है।',
    kn: 'ಈ ಕೋಡ್ ಉಳಿಸಿ. ನಂತರ ನಿಮ್ಮ ದೂರು ಪರಿಶೀಲಿಸಲು ಇದೊಂದೇ ಮಾರ್ಗ, ಮತ್ತು ಇದು ಯಾವುದೇ ಗುರುತಿಗೆ ಲಿಂಕ್ ಆಗಿಲ್ಲ.',
  },
  mergedNotice: {
    en: 'Someone already reported this nearby. Your report was merged into that one so it gets prioritised.',
    hi: 'किसी ने पास में यह पहले ही दर्ज किया है। आपकी शिकायत उसी में जोड़ दी गई ताकि उसे प्राथमिकता मिले।',
    kn: 'ಹತ್ತಿರದಲ್ಲಿ ಯಾರೋ ಇದನ್ನು ಈಗಾಗಲೇ ವರದಿ ಮಾಡಿದ್ದಾರೆ. ಆದ್ಯತೆ ಸಿಗುವಂತೆ ನಿಮ್ಮ ದೂರನ್ನು ಅದಕ್ಕೆ ಸೇರಿಸಲಾಗಿದೆ.',
  },

  boardTitle: { en: 'Public status board', hi: 'सार्वजनिक स्थिति बोर्ड', kn: 'ಸಾರ್ವಜನಿಕ ಸ್ಥಿತಿ ಫಲಕ' },
  filterAll: { en: 'All', hi: 'सभी', kn: 'ಎಲ್ಲಾ' },
  reportsCount: { en: 'reports', hi: 'शिकायतें', kn: 'ದೂರುಗಳು' },
  noIssues: { en: 'No issues match this filter.', hi: 'इस फ़िल्टर से कोई समस्या मेल नहीं खाती।', kn: 'ಈ ಫಿಲ್ಟರ್‌ಗೆ ಯಾವುದೇ ಸಮಸ್ಯೆ ಹೊಂದಿಕೆಯಾಗುತ್ತಿಲ್ಲ.' },
  dueBy: { en: 'Due by', hi: 'नियत तिथि', kn: 'ಗಡುವು' },
  reportedTimes: { en: 'reported by', hi: 'द्वारा दर्ज', kn: 'ವರದಿ ಮಾಡಿದವರು' },
  people: { en: 'people', hi: 'लोग', kn: 'ಜನರು' },

  trackTitle: { en: 'Track your report', hi: 'अपनी शिकायत ट्रैक करें', kn: 'ನಿಮ್ಮ ದೂರು ಟ್ರ್ಯಾಕ್ ಮಾಡಿ' },
  trackPlaceholder: { en: 'Paste your tracking code', hi: 'अपना ट्रैकिंग कोड पेस्ट करें', kn: 'ನಿಮ್ಮ ಟ್ರ್ಯಾಕಿಂಗ್ ಕೋಡ್ ಅಂಟಿಸಿ' },
  trackButton: { en: 'Check status', hi: 'स्थिति देखें', kn: 'ಸ್ಥಿತಿ ಪರಿಶೀಲಿಸಿ' },
  trackNotFound: { en: 'No report found for that code.', hi: 'उस कोड के लिए कोई शिकायत नहीं मिली।', kn: 'ಆ ಕೋಡ್‌ಗೆ ಯಾವುದೇ ದೂರು ಕಂಡುಬಂದಿಲ್ಲ.' },

  statusReported: { en: 'Reported', hi: 'दर्ज', kn: 'ವರದಿಯಾಗಿದೆ' },
  statusAcknowledged: { en: 'Acknowledged', hi: 'स्वीकृत', kn: 'ಸ್ವೀಕರಿಸಲಾಗಿದೆ' },
  statusInProgress: { en: 'In progress', hi: 'कार्य जारी', kn: 'ಪ್ರಗತಿಯಲ್ಲಿದೆ' },
  statusResolved: { en: 'Resolved', hi: 'हल हो गया', kn: 'ಪರಿಹರಿಸಲಾಗಿದೆ' },
  statusOverdue: { en: 'Overdue', hi: 'विलंबित', kn: 'ವಿಳಂಬವಾಗಿದೆ' },

  shareCard: { en: 'Get a shareable card', hi: 'साझा करने योग्य कार्ड लें', kn: 'ಹಂಚಿಕೊಳ್ಳಬಹುದಾದ ಕಾರ್ಡ್ ಪಡೆಯಿರಿ' },
  shareHelp: {
    en: 'This platform never posts on your behalf. Share it yourself if you choose to.',
    hi: 'यह प्लेटफ़ॉर्म आपकी ओर से कभी पोस्ट नहीं करता। यदि आप चाहें तो स्वयं साझा करें।',
    kn: 'ಈ ವೇದಿಕೆ ನಿಮ್ಮ ಪರವಾಗಿ ಎಂದಿಗೂ ಪೋಸ್ಟ್ ಮಾಡುವುದಿಲ್ಲ. ನೀವು ಬಯಸಿದರೆ ನೀವೇ ಹಂಚಿಕೊಳ್ಳಿ.',
  },
  copy: { en: 'Copy', hi: 'कॉपी करें', kn: 'ನಕಲಿಸಿ' },
  copied: { en: 'Copied', hi: 'कॉपी हो गया', kn: 'ನಕಲಿಸಲಾಗಿದೆ' },

  email: { en: 'Email', hi: 'ईमेल', kn: 'ಇಮೇಲ್' },
  password: { en: 'Password', hi: 'पासवर्ड', kn: 'ಪಾಸ್‌ವರ್ಡ್' },
  login: { en: 'Log in', hi: 'लॉग इन', kn: 'ಲಾಗಿನ್' },
  logout: { en: 'Log out', hi: 'लॉग आउट', kn: 'ಲಾಗ್ ಔಟ್' },
  loginFailed: { en: 'Invalid email or password.', hi: 'अमान्य ईमेल या पासवर्ड।', kn: 'ಅಮಾನ್ಯ ಇಮೇಲ್ ಅಥವಾ ಪಾಸ್‌ವರ್ಡ್.' },

  queueTitle: { en: 'Assigned issues', hi: 'सौंपी गई समस्याएँ', kn: 'ನಿಯೋಜಿತ ಸಮಸ್ಯೆಗಳು' },
  acknowledge: { en: 'Acknowledge', hi: 'स्वीकार करें', kn: 'ಸ್ವೀಕರಿಸಿ' },
  startWork: { en: 'Start work', hi: 'कार्य शुरू करें', kn: 'ಕೆಲಸ ಪ್ರಾರಂಭಿಸಿ' },
  resolveWithProof: { en: 'Resolve with proof photo', hi: 'प्रमाण फ़ोटो के साथ हल करें', kn: 'ಪುರಾವೆ ಫೋಟೋದೊಂದಿಗೆ ಪರಿಹರಿಸಿ' },
  proofRequired: {
    en: 'A proof photo is required to mark an issue resolved.',
    hi: 'समस्या हल के रूप में चिह्नित करने के लिए प्रमाण फ़ोटो आवश्यक है।',
    kn: 'ಸಮಸ್ಯೆಯನ್ನು ಪರಿಹರಿಸಲಾಗಿದೆ ಎಂದು ಗುರುತಿಸಲು ಪುರಾವೆ ಫೋಟೋ ಅಗತ್ಯವಿದೆ.',
  },
  required: { en: 'Required', hi: 'आवश्यक', kn: 'ಅಗತ್ಯವಿದೆ' },
  errorGeneric: { en: 'Something went wrong. Please try again.', hi: 'कुछ गलत हुआ। कृपया पुनः प्रयास करें।', kn: 'ಏನೋ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.' },
} as const

export type StringKey = keyof typeof STRINGS

type I18nValue = {
  lang: Lang
  setLang: (l: Lang) => void
  t: (key: StringKey) => string
}

const I18nContext = createContext<I18nValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const stored = localStorage.getItem('lang')
    return stored === 'hi' || stored === 'kn' ? stored : 'en'
  })

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((l: Lang) => {
    localStorage.setItem('lang', l)
    setLangState(l)
  }, [])

  const t = useCallback((key: StringKey) => STRINGS[key][lang], [lang])

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n must be used inside I18nProvider')
  return ctx
}
