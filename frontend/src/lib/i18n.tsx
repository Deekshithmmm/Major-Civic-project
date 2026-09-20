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
    en: 'Location data is removed before your file is stored, and sound is removed from videos. Faces are blurred in photos, but not in videos.',
    hi: 'आपकी फ़ाइल संग्रहीत होने से पहले स्थान डेटा हटा दिया जाता है, और वीडियो से आवाज़ हटा दी जाती है। फ़ोटो में चेहरे धुंधले किए जाते हैं, लेकिन वीडियो में नहीं।',
    kn: 'ನಿಮ್ಮ ಫೈಲ್ ಸಂಗ್ರಹಿಸುವ ಮೊದಲು ಸ್ಥಳ ಡೇಟಾವನ್ನು ತೆಗೆದುಹಾಕಲಾಗುತ್ತದೆ, ಮತ್ತು ವೀಡಿಯೊಗಳಿಂದ ಧ್ವನಿಯನ್ನು ತೆಗೆದುಹಾಕಲಾಗುತ್ತದೆ. ಫೋಟೋಗಳಲ್ಲಿ ಮುಖಗಳನ್ನು ಮಸುಕುಗೊಳಿಸಲಾಗುತ್ತದೆ, ಆದರೆ ವೀಡಿಯೊಗಳಲ್ಲಿ ಅಲ್ಲ.',
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
    en: 'Uploaded. Removing location data from your file — this takes a few seconds.',
    hi: 'अपलोड हो गया। आपकी फ़ाइल से स्थान डेटा हटाया जा रहा है — इसमें कुछ सेकंड लगते हैं।',
    kn: 'ಅಪ್‌ಲೋಡ್ ಆಗಿದೆ. ನಿಮ್ಮ ಫೈಲ್‌ನಿಂದ ಸ್ಥಳ ಡೇಟಾವನ್ನು ತೆಗೆದುಹಾಕಲಾಗುತ್ತಿದೆ — ಇದಕ್ಕೆ ಕೆಲವು ಸೆಕೆಂಡುಗಳು ಬೇಕು.',
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
  trackPlaceholder: { en: 'Enter your 10-digit code', hi: 'अपना 10 अंकों का कोड दर्ज करें', kn: 'ನಿಮ್ಮ 10 ಅಂಕಿಯ ಕೋಡ್ ನಮೂದಿಸಿ' },
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

  // --- Home ---
  homeIntro: {
    en: 'Report civic problems, corruption and violations. No account is ever needed, and reports are anonymous by default.',
    hi: 'नागरिक समस्याएँ, भ्रष्टाचार और उल्लंघन दर्ज करें। किसी खाते की आवश्यकता नहीं, और शिकायतें डिफ़ॉल्ट रूप से गुमनाम हैं।',
    kn: 'ನಾಗರಿಕ ಸಮಸ್ಯೆಗಳು, ಭ್ರಷ್ಟಾಚಾರ ಮತ್ತು ಉಲ್ಲಂಘನೆಗಳನ್ನು ವರದಿ ಮಾಡಿ. ಖಾತೆ ಅಗತ್ಯವಿಲ್ಲ, ಮತ್ತು ದೂರುಗಳು ಪೂರ್ವನಿಯೋಜಿತವಾಗಿ ಅನಾಮಧೇಯ.',
  },
  infraTitle: { en: 'Civic infrastructure', hi: 'नागरिक अवसंरचना', kn: 'ನಾಗರಿಕ ಮೂಲಸೌಕರ್ಯ' },
  homeInfraBody: {
    en: 'Potholes, street lights, drains, garbage, water leaks. Routed to the responsible desk with a deadline, and tracked publicly.',
    hi: 'गड्ढे, स्ट्रीट लाइट, नालियाँ, कचरा, पानी का रिसाव। समय-सीमा के साथ ज़िम्मेदार विभाग को भेजा जाता है और सार्वजनिक रूप से ट्रैक किया जाता है।',
    kn: 'ಗುಂಡಿಗಳು, ಬೀದಿ ದೀಪಗಳು, ಚರಂಡಿಗಳು, ಕಸ, ನೀರಿನ ಸೋರಿಕೆ. ಗಡುವಿನೊಂದಿಗೆ ಜವಾಬ್ದಾರ ಇಲಾಖೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ ಮತ್ತು ಸಾರ್ವಜನಿಕವಾಗಿ ಟ್ರ್ಯಾಕ್ ಮಾಡಲಾಗುತ್ತದೆ.',
  },
  homeCorruptionTitle: { en: 'Corruption reporting', hi: 'भ्रष्टाचार की शिकायत', kn: 'ಭ್ರಷ್ಟಾಚಾರ ವರದಿ' },
  homeCorruptionBody: {
    en: 'Bribery or misconduct by officials, reported anonymously and routed to an independent oversight body — never to the accused.',
    hi: 'अधिकारियों द्वारा रिश्वत या कदाचार, गुमनाम रूप से दर्ज और स्वतंत्र निगरानी संस्था को भेजा जाता है — कभी आरोपी को नहीं।',
    kn: 'ಅಧಿಕಾರಿಗಳ ಲಂಚ ಅಥವಾ ದುರ್ನಡತೆ, ಅನಾಮಧೇಯವಾಗಿ ವರದಿಯಾಗಿ ಸ್ವತಂತ್ರ ಮೇಲ್ವಿಚಾರಣಾ ಸಂಸ್ಥೆಗೆ ಕಳುಹಿಸಲಾಗುತ್ತದೆ — ಎಂದಿಗೂ ಆರೋಪಿಗೆ ಅಲ್ಲ.',
  },
  homeCorruptionCta: { en: 'Open the feed', hi: 'फ़ीड खोलें', kn: 'ಫೀಡ್ ತೆರೆಯಿರಿ' },
  homeViolationsTitle: { en: 'Violations and enforcement', hi: 'उल्लंघन और प्रवर्तन', kn: 'ಉಲ್ಲಂಘನೆ ಮತ್ತು ಜಾರಿ' },
  homeViolationsBody: {
    en: 'Littering, illegal dumping, footpath parking. An officer reviews the evidence — the system never issues a fine on its own.',
    hi: 'कचरा फेंकना, अवैध डंपिंग, फुटपाथ पर पार्किंग। एक अधिकारी साक्ष्य की समीक्षा करता है — सिस्टम स्वयं कभी जुर्माना जारी नहीं करता।',
    kn: 'ಕಸ ಎಸೆಯುವುದು, ಅಕ್ರಮ ಡಂಪಿಂಗ್, ಪಾದಚಾರಿ ಮಾರ್ಗದಲ್ಲಿ ಪಾರ್ಕಿಂಗ್. ಅಧಿಕಾರಿ ಸಾಕ್ಷ್ಯ ಪರಿಶೀಲಿಸುತ್ತಾರೆ — ವ್ಯವಸ್ಥೆ ಸ್ವತಃ ದಂಡ ವಿಧಿಸುವುದಿಲ್ಲ.',
  },
  homeViolationsCta: { en: 'Report a violation', hi: 'उल्लंघन दर्ज करें', kn: 'ಉಲ್ಲಂಘನೆ ವರದಿ ಮಾಡಿ' },
  homeEmergencyTitle: { en: 'Emergency and accountability', hi: 'आपातकाल और जवाबदेही', kn: 'ತುರ್ತು ಮತ್ತು ಹೊಣೆಗಾರಿಕೆ' },
  homeEmergencyBody: {
    en: 'If someone is in danger, call 112 first. Also shows how each police station responds to the reports it receives.',
    hi: 'यदि कोई ख़तरे में है, तो पहले 112 पर कॉल करें। यह भी दिखाता है कि प्रत्येक पुलिस स्टेशन प्राप्त शिकायतों पर कैसे प्रतिक्रिया देता है।',
    kn: 'ಯಾರಾದರೂ ಅಪಾಯದಲ್ಲಿದ್ದರೆ ಮೊದಲು 112 ಗೆ ಕರೆ ಮಾಡಿ. ಪ್ರತಿ ಠಾಣೆ ಸ್ವೀಕರಿಸಿದ ದೂರುಗಳಿಗೆ ಹೇಗೆ ಸ್ಪಂದಿಸುತ್ತದೆ ಎಂಬುದನ್ನೂ ತೋರಿಸುತ್ತದೆ.',
  },
  homeEmergencyCta: { en: 'Open', hi: 'खोलें', kn: 'ತೆರೆಯಿರಿ' },
  homeNoAccount: {
    en: 'Officials sign in to review reports. Citizens never do.',
    hi: 'अधिकारी शिकायतों की समीक्षा के लिए साइन इन करते हैं। नागरिक कभी नहीं।',
    kn: 'ಅಧಿಕಾರಿಗಳು ದೂರುಗಳನ್ನು ಪರಿಶೀಲಿಸಲು ಸೈನ್ ಇನ್ ಮಾಡುತ್ತಾರೆ. ನಾಗರಿಕರು ಎಂದಿಗೂ ಇಲ್ಲ.',
  },

  // --- Nav ---
  navHome: { en: 'Home', hi: 'होम', kn: 'ಮುಖಪುಟ' },
  navCorruption: { en: 'Corruption', hi: 'भ्रष्टाचार', kn: 'ಭ್ರಷ್ಟಾಚಾರ' },
  navViolations: { en: 'Violations', hi: 'उल्लंघन', kn: 'ಉಲ್ಲಂಘನೆ' },
  navEmergency: { en: 'Emergency', hi: 'आपातकाल', kn: 'ತುರ್ತು' },

  // --- Module 2 ---
  corrReportTitle: { en: 'Report corruption anonymously', hi: 'भ्रष्टाचार की गुमनाम शिकायत करें', kn: 'ಅನಾಮಧೇಯವಾಗಿ ಭ್ರಷ್ಟಾಚಾರ ವರದಿ ಮಾಡಿ' },
  corrAnonIntro: {
    en: 'No account, no phone number, no email. Your IP address is not recorded, and file metadata is removed before storage.',
    hi: 'कोई खाता नहीं, कोई फ़ोन नंबर नहीं, कोई ईमेल नहीं। आपका IP पता दर्ज नहीं किया जाता, और संग्रह से पहले फ़ाइल मेटाडेटा हटा दिया जाता है।',
    kn: 'ಖಾತೆ ಇಲ್ಲ, ಫೋನ್ ಸಂಖ್ಯೆ ಇಲ್ಲ, ಇಮೇಲ್ ಇಲ್ಲ. ನಿಮ್ಮ IP ವಿಳಾಸ ದಾಖಲಾಗುವುದಿಲ್ಲ, ಮತ್ತು ಸಂಗ್ರಹಣೆಗೂ ಮೊದಲು ಫೈಲ್ ಮೆಟಾಡೇಟಾ ತೆಗೆದುಹಾಕಲಾಗುತ್ತದೆ.',
  },
  corrDepartment: { en: 'Department', hi: 'विभाग', kn: 'ಇಲಾಖೆ' },
  corrDesignation: { en: 'Designation', hi: 'पद', kn: 'ಹುದ್ದೆ' },
  corrPartyType: { en: 'Who is being reported', hi: 'किसकी शिकायत है', kn: 'ಯಾರ ಬಗ್ಗೆ ದೂರು' },
  corrNoNames: {
    en: 'Do not enter anyone’s name. This platform publishes department and designation only.',
    hi: 'किसी का नाम दर्ज न करें। यह प्लेटफ़ॉर्म केवल विभाग और पद प्रकाशित करता है।',
    kn: 'ಯಾರ ಹೆಸರನ್ನೂ ನಮೂದಿಸಬೇಡಿ. ಈ ವೇದಿಕೆ ಇಲಾಖೆ ಮತ್ತು ಹುದ್ದೆಯನ್ನು ಮಾತ್ರ ಪ್ರಕಟಿಸುತ್ತದೆ.',
  },
  corrRoutedTo: { en: 'This report will be sent to', hi: 'यह शिकायत भेजी जाएगी', kn: 'ಈ ದೂರು ಕಳುಹಿಸಲಾಗುವುದು' },
  corrPoliceNever: {
    en: 'Local police are never notified about reports against police personnel.',
    hi: 'पुलिसकर्मियों के विरुद्ध शिकायतों की सूचना स्थानीय पुलिस को कभी नहीं दी जाती।',
    kn: 'ಪೊಲೀಸ್ ಸಿಬ್ಬಂದಿ ವಿರುದ್ಧದ ದೂರುಗಳ ಬಗ್ಗೆ ಸ್ಥಳೀಯ ಪೊಲೀಸರಿಗೆ ಎಂದಿಗೂ ತಿಳಿಸಲಾಗುವುದಿಲ್ಲ.',
  },
  corrAreaTitle: { en: 'Approximate area', hi: 'अनुमानित क्षेत्र', kn: 'ಅಂದಾಜು ಪ್ರದೇಶ' },
  corrAreaHelp: {
    en: 'Pick a point on the map. Only a rough area is saved, never an exact spot, and your device location is never read.',
    hi: 'मानचित्र पर एक बिंदु चुनें। केवल एक मोटा क्षेत्र सहेजा जाता है, सटीक स्थान कभी नहीं, और आपके डिवाइस का स्थान कभी नहीं पढ़ा जाता।',
    kn: 'ನಕ್ಷೆಯಲ್ಲಿ ಒಂದು ಬಿಂದು ಆಯ್ಕೆಮಾಡಿ. ಅಂದಾಜು ಪ್ರದೇಶ ಮಾತ್ರ ಉಳಿಸಲಾಗುತ್ತದೆ, ನಿಖರ ಸ್ಥಳ ಎಂದಿಗೂ ಅಲ್ಲ, ಮತ್ತು ನಿಮ್ಮ ಸಾಧನದ ಸ್ಥಳ ಓದಲಾಗುವುದಿಲ್ಲ.',
  },
  corrSubmitted: {
    en: 'Report received. It is reviewed by a moderator before it can appear publicly.',
    hi: 'शिकायत प्राप्त हुई। सार्वजनिक रूप से दिखने से पहले एक मॉडरेटर इसकी समीक्षा करता है।',
    kn: 'ದೂರು ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ಸಾರ್ವಜನಿಕವಾಗಿ ಕಾಣಿಸುವ ಮೊದಲು ಮಾಡರೇಟರ್ ಪರಿಶೀಲಿಸುತ್ತಾರೆ.',
  },
  corrFeedTitle: { en: 'Corruption reports', hi: 'भ्रष्टाचार की शिकायतें', kn: 'ಭ್ರಷ್ಟಾಚಾರ ದೂರುಗಳು' },
  corrFeedEmpty: {
    en: 'Nothing published yet. Reports appear here only after a moderator approves them.',
    hi: 'अभी कुछ प्रकाशित नहीं हुआ। मॉडरेटर की मंज़ूरी के बाद ही शिकायतें यहाँ दिखती हैं।',
    kn: 'ಇನ್ನೂ ಏನೂ ಪ್ರಕಟವಾಗಿಲ್ಲ. ಮಾಡರೇಟರ್ ಅನುಮೋದಿಸಿದ ನಂತರವೇ ದೂರುಗಳು ಇಲ್ಲಿ ಕಾಣಿಸುತ್ತವೆ.',
  },
  corrFeedDisclaimer: {
    en: 'These are allegations, not findings. The platform never names an individual.',
    hi: 'ये आरोप हैं, निष्कर्ष नहीं। यह प्लेटफ़ॉर्म कभी किसी व्यक्ति का नाम नहीं बताता।',
    kn: 'ಇವು ಆರೋಪಗಳು, ತೀರ್ಮಾನಗಳಲ್ಲ. ವೇದಿಕೆ ಎಂದಿಗೂ ವ್ಯಕ್ತಿಯ ಹೆಸರನ್ನು ಹೇಳುವುದಿಲ್ಲ.',
  },
  badgeUnverified: { en: 'Unverified allegation', hi: 'असत्यापित आरोप', kn: 'ಪರಿಶೀಲಿಸದ ಆರೋಪ' },
  badgeInvestigating: { en: 'Under investigation', hi: 'जाँच जारी', kn: 'ತನಿಖೆಯಲ್ಲಿದೆ' },
  badgeActionTaken: { en: 'Action taken', hi: 'कार्रवाई की गई', kn: 'ಕ್ರಮ ಕೈಗೊಳ್ಳಲಾಗಿದೆ' },
  badgeDismissed: { en: 'Dismissed', hi: 'खारिज', kn: 'ವಜಾಗೊಳಿಸಲಾಗಿದೆ' },

  // --- Module 1 ---
  violReportTitle: { en: 'Report a civic violation', hi: 'नागरिक उल्लंघन दर्ज करें', kn: 'ನಾಗರಿಕ ಉಲ್ಲಂಘನೆ ವರದಿ ಮಾಡಿ' },
  violIntro: {
    en: 'An authorised officer reviews your evidence and decides. No fine is ever issued automatically.',
    hi: 'एक अधिकृत अधिकारी आपके साक्ष्य की समीक्षा कर निर्णय लेता है। कोई जुर्माना स्वतः जारी नहीं होता।',
    kn: 'ಅಧಿಕೃತ ಅಧಿಕಾರಿ ನಿಮ್ಮ ಸಾಕ್ಷ್ಯ ಪರಿಶೀಲಿಸಿ ನಿರ್ಧರಿಸುತ್ತಾರೆ. ಯಾವುದೇ ದಂಡ ಸ್ವಯಂಚಾಲಿತವಾಗಿ ವಿಧಿಸಲಾಗುವುದಿಲ್ಲ.',
  },
  violClass: { en: 'What did you see', hi: 'आपने क्या देखा', kn: 'ನೀವು ಏನು ನೋಡಿದಿರಿ' },
  // --- Module 4 ---
  emgTitle: { en: 'Report a crime or emergency', hi: 'अपराध या आपात स्थिति की सूचना दें', kn: 'ಅಪರಾಧ ಅಥವಾ ತುರ್ತು ವರದಿ ಮಾಡಿ' },
  emgTierA: { en: 'Someone is in danger right now', hi: 'कोई अभी ख़तरे में है', kn: 'ಯಾರಾದರೂ ಈಗ ಅಪಾಯದಲ್ಲಿದ್ದಾರೆ' },
  emgTierABody: {
    en: 'An assault, violence, or an injured person. Call for help first — do not stop to film.',
    hi: 'हमला, हिंसा, या घायल व्यक्ति। पहले मदद के लिए कॉल करें — फ़िल्म करने के लिए न रुकें।',
    kn: 'ಹಲ್ಲೆ, ಹಿಂಸೆ ಅಥವಾ ಗಾಯಗೊಂಡ ವ್ಯಕ್ತಿ. ಮೊದಲು ಸಹಾಯಕ್ಕೆ ಕರೆ ಮಾಡಿ — ಚಿತ್ರೀಕರಿಸಲು ನಿಲ್ಲಬೇಡಿ.',
  },
  emgTierB: { en: 'It already happened, or is ongoing', hi: 'यह हो चुका है, या जारी है', kn: 'ಈಗಾಗಲೇ ನಡೆದಿದೆ ಅಥವಾ ನಡೆಯುತ್ತಿದೆ' },
  emgTierBBody: {
    en: 'A recorded incident, something discovered, narcotics or trafficking. Send it to investigators.',
    hi: 'रिकॉर्ड की गई घटना, कुछ मिला, नशीले पदार्थ या तस्करी। इसे जाँचकर्ताओं को भेजें।',
    kn: 'ದಾಖಲಾದ ಘಟನೆ, ಪತ್ತೆಯಾದದ್ದು, ಮಾದಕವಸ್ತು ಅಥವಾ ಕಳ್ಳಸಾಗಣೆ. ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಕಳುಹಿಸಿ.',
  },
  emgCall112: { en: 'Call 112 now', hi: 'अभी 112 पर कॉल करें', kn: 'ಈಗ 112 ಗೆ ಕರೆ ಮಾಡಿ' },
  emgCallHelp: {
    en: 'Read out your location to the operator. If speaking aloud is unsafe, stay on the line and the operator will still receive the call.',
    hi: 'ऑपरेटर को अपना स्थान बताएं। यदि बोलना सुरक्षित नहीं है, तो लाइन पर बने रहें, ऑपरेटर को कॉल फिर भी मिलेगी।',
    kn: 'ಆಪರೇಟರ್‌ಗೆ ನಿಮ್ಮ ಸ್ಥಳ ತಿಳಿಸಿ. ಮಾತನಾಡುವುದು ಸುರಕ್ಷಿತವಲ್ಲದಿದ್ದರೆ, ಲೈನ್‌ನಲ್ಲಿಯೇ ಇರಿ, ಕರೆ ತಲುಪುತ್ತದೆ.',
  },
  emgAfterCall: {
    en: 'I have called for help — I also have evidence to send',
    hi: 'मैंने मदद के लिए कॉल कर लिया है — मेरे पास भेजने के लिए साक्ष्य भी है',
    kn: 'ನಾನು ಸಹಾಯಕ್ಕೆ ಕರೆ ಮಾಡಿದ್ದೇನೆ — ಕಳುಹಿಸಲು ಸಾಕ್ಷ್ಯವೂ ಇದೆ',
  },
  emgCategory: { en: 'What are you reporting', hi: 'आप क्या सूचित कर रहे हैं', kn: 'ನೀವು ಏನು ವರದಿ ಮಾಡುತ್ತಿದ್ದೀರಿ' },
  emgMinorStop: { en: 'We cannot accept this here', hi: 'हम इसे यहाँ स्वीकार नहीं कर सकते', kn: 'ನಾವು ಇದನ್ನು ಇಲ್ಲಿ ಸ್ವೀಕರಿಸಲಾಗುವುದಿಲ್ಲ' },
  emgMinorStopBody: {
    en: 'If a child is involved, this platform must not receive or store the material — doing so is itself an offence, including for us. These services can act immediately.',
    hi: 'यदि कोई बच्चा शामिल है, तो यह प्लेटफ़ॉर्म सामग्री प्राप्त या संग्रहीत नहीं कर सकता — ऐसा करना स्वयं एक अपराध है, हमारे लिए भी। ये सेवाएँ तुरंत कार्रवाई कर सकती हैं।',
    kn: 'ಮಗು ಒಳಗೊಂಡಿದ್ದರೆ, ಈ ವೇದಿಕೆ ಆ ಸಾಮಗ್ರಿಯನ್ನು ಸ್ವೀಕರಿಸುವಂತಿಲ್ಲ ಅಥವಾ ಸಂಗ್ರಹಿಸುವಂತಿಲ್ಲ — ಹಾಗೆ ಮಾಡುವುದು ನಮಗೂ ಅಪರಾಧ. ಈ ಸೇವೆಗಳು ತಕ್ಷಣ ಕ್ರಮ ಕೈಗೊಳ್ಳಬಲ್ಲವು.',
  },
  emgEvidenceOptional: {
    en: 'Evidence (optional) — a report without a file reaches investigators just the same.',
    hi: 'साक्ष्य (वैकल्पिक) — बिना फ़ाइल की शिकायत भी जाँचकर्ताओं तक उसी तरह पहुँचती है।',
    kn: 'ಸಾಕ್ಷ್ಯ (ಐಚ್ಛಿಕ) — ಫೈಲ್ ಇಲ್ಲದ ದೂರೂ ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಅಷ್ಟೇ ತಲುಪುತ್ತದೆ.',
  },
  emgSubmitted: { en: 'Report sent to investigators', hi: 'शिकायत जाँचकर्ताओं को भेजी गई', kn: 'ದೂರು ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ' },
  emgRoutedTo: { en: 'Sent to', hi: 'भेजा गया', kn: 'ಕಳುಹಿಸಲಾಗಿದೆ' },
  emgSupportTitle: { en: 'Help available to you now', hi: 'अभी आपके लिए उपलब्ध सहायता', kn: 'ಈಗ ನಿಮಗೆ ಲಭ್ಯವಿರುವ ಸಹಾಯ' },
  emgNeverPublic: {
    en: 'Your evidence is never published. It goes to investigators under a sealed chain of custody.',
    hi: 'आपका साक्ष्य कभी प्रकाशित नहीं होता। यह सीलबंद कस्टडी श्रृंखला के तहत जाँचकर्ताओं को जाता है।',
    kn: 'ನಿಮ್ಮ ಸಾಕ್ಷ್ಯ ಎಂದಿಗೂ ಪ್ರಕಟವಾಗುವುದಿಲ್ಲ. ಇದು ಮೊಹರು ಮಾಡಿದ ಕಸ್ಟಡಿ ಸರಪಳಿಯಡಿ ತನಿಖಾಧಿಕಾರಿಗಳಿಗೆ ಹೋಗುತ್ತದೆ.',
  },
  navTransparency: { en: 'Accountability', hi: 'जवाबदेही', kn: 'ಹೊಣೆಗಾರಿಕೆ' },

  violSubmitted: {
    en: 'Evidence received. It is now waiting for an officer to review it.',
    hi: 'साक्ष्य प्राप्त हुआ। अब यह अधिकारी की समीक्षा की प्रतीक्षा में है।',
    kn: 'ಸಾಕ್ಷ್ಯ ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ಈಗ ಅಧಿಕಾರಿಯ ಪರಿಶೀಲನೆಗೆ ಕಾಯುತ್ತಿದೆ.',
  },
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
