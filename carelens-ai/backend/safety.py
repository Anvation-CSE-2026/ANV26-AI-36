"""Safety guard for everything typed to the AI assistant.

Purpose: nobody (the user, another family member, or text pasted from elsewhere) can use the assistant to put the
user or a patient at risk, or to get around the app's privacy rules. A request that trips the guard is NOT sent to
any AI provider. It is "abandoned": the person gets a short fixed message instead (in their language), and a
security event is recorded (category only, never the text).

This is a first, deterministic layer. The AI's own system prompt carries the same rules as a second layer, and the
AI's reply is screened again before it is shown (screen_output).

Design notes
* Rules are deliberately narrow so ordinary questions are never blocked: "What does my overdose warning mean?",
  "What is my dose of metformin?", "Show all my records" all pass.
* Text is normalised first (Unicode compatibility form, no zero-width characters, lower case, single spaces),
  so spacing tricks and look-alike characters don't slip past.
"""
import re
import unicodedata
from typing import NamedTuple, Optional

SELF_HARM = "self_harm"
HARM_OTHERS = "harm_others"
PRIVACY = "privacy_attack"
INJECTION = "prompt_injection"

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def normalise(text):
    t = unicodedata.normalize("NFKC", text or "").translate(_ZERO_WIDTH).lower()
    t = re.sub(r"[‘’ʼ`]", "'", t)
    # Keep letters, combining marks (vowel signs in Indic scripts), digits and spaces; drop other punctuation/symbols.
    t = "".join(ch if (unicodedata.category(ch)[0] in "LMNZ" or ch in "'@.-_") else " " for ch in t)
    return re.sub(r"\s+", " ", t).strip()


_SPACED = re.compile(r"(?<![^\W\d_])(?:[^\W\d_]\s){3,}[^\W\d_](?![^\W\d_])")


def _variants(text):
    """The normal form, plus a form with 'k i l l'-style spaced-out letters joined back together."""
    t = normalise(text)
    joined = _SPACED.sub(lambda m: re.sub(r"\s", "", m.group(0)), t)
    return (t,) if joined == t else (t, joined)


def _c(*patterns):
    return [re.compile(p, re.I | re.U) for p in patterns]


_RULES = {
    SELF_HARM: _c(
        r"\b(?:kill|hurt|harm|injure|cut|poison|end|stab|hang|drown)\s+(?:my\s*self|myself)\b",
        r"\b(?:end|take)\s+my\s+(?:own\s+)?life\b",
        r"\bsuicid(?:e|al)\b", r"\bself[\s-]?harm\b", r"\bself[\s-]?injur",
        r"\bwant(?:ed)?\s+to\s+(?:die|disappear|be\s+dead)\b",
        r"\b(?:don'?t|do\s+not|no\s+longer)\s+want\s+to\s+(?:live|be\s+alive|exist|wake\s+up)\b",
        r"\b(?:better\s+off\s+dead|end\s+it\s+all|no\s+reason\s+to\s+live)\b",
        r"\b(?:lethal|fatal|deadly)\s+(?:dose|amount|quantity|overdose)\b",
        r"\bhow\s+(?:many|much)\b.{0,70}\b(?:to|would|will|can|could)\s+(?:kill|die|be\s+fatal|be\s+lethal|overdose)\b",
        r"\b(?:how\s+to|ways?\s+to|best\s+way\s+to|easiest\s+way\s+to)\s+(?:overdose|die|commit)\b",
        r"\boverdose\b.{0,30}\b(?:on\s+purpose|deliberately|intentionally|to\s+(?:die|kill|sleep\s+forever))\b",
        # Hindi / Marathi, Kannada, Tamil, Telugu, Malayalam, Bengali
        r"आत्महत्या", r"मरना\s+चाह", r"जान\s+दे\s*(?:दूँ|दूं|ना)", r"खुद\s+को\s+(?:मार|खत्म|ख़त्म)", r"जीना\s+नहीं\s+चाह",
        r"ಆತ್ಮಹತ್ಯೆ", r"ಸಾಯಲು", r"ಸಾಯಬೇಕು", r"தற்கொலை", r"ఆత్మహత్య", r"ആത്മഹത്യ", r"আত্মহত্যা",
    ),
    HARM_OTHERS: _c(
        r"\b(?:poison|drug|sedate|spike|overdose)\s+(?:someone|somebody|him|her|them|my\s+\w+|his|her|their|the\s+(?:patient|baby|child|kid))\b",
        r"\bhow\s+to\s+(?:kill|murder|hurt|harm|injure|poison|abuse|beat|hit|silence|get\s+rid\s+of)\s+(?:a|an|my|his|her|their|some\w*|the)\b",
        r"\b(?:kill|murder)\s+(?:him|her|them|my\s+\w+|someone|somebody)\b",
        r"\bmake\s+(?:him|her|them|my\s+\w+)\s+(?:sick|ill|die|sleep\s+forever|unconscious|collapse)\b",
        r"\b(?:give|put|add|mix|feed|slip)\b.{0,70}\b(?:secretly|without\s+(?:him|her|them|anyone|the\s+person|their)\b.{0,12}(?:knowing|noticing|realising|realizing)|without\s+knowing)\b",
        r"\b(?:secretly|without\s+(?:him|her|them|their)\s+(?:knowing|noticing))\b.{0,70}\b(?:give|put|add|mix|feed|slip)\b",
        r"\b(?:skip|withhold|hide|throw\s+away|stop\s+giving)\b.{0,30}\b(?:his|her|their|mother'?s|father'?s|patient'?s|grand\w+'?s)\s+(?:medicines?|medications?|insulin|tablets?|pills?)\b.{0,50}\b(?:so\s+(?:he|she|they)\s+(?:die|get\s+worse|suffer|collapse)|to\s+(?:harm|hurt|kill))\b",
    ),
    PRIVACY: _c(
        r"\b(?:bypass|circumvent|get\s+around|override)\b.{0,25}\b(?:sharing|permissions?|privacy|authori[sz]ation|authentication|access\s+controls?|security)\b",
        r"\b(?:other|another|different)\s+(?:users?|members?|patients?|accounts?|famil\w+\s+members?)'?s?\s+(?:\w+\s+){0,2}(?:records?|data|passwords?|documents?|reports?|medicines?|health|information|details|logins?|messages?|chats?)\b",
        r"\b(?:someone|somebody)\s+else'?s\s+(?:\w+\s+){0,2}(?:records?|data|passwords?|accounts?|logins?|documents?|reports?|medicines?|chats?)\b",
        r"\b(?:access|open|read|see|view|get|download|check)\b.{0,50}\b(?:without|bypass(?:ing)?|despite|behind)\s+(?:\w+\s+){0,2}(?:permission|consent|sharing|authori[sz]ation|knowing|their\s+knowledge)\b",
        r"\b(?:hack|crack|break\s+into|brute[\s-]?force|steal|phish|impersonate|spy\s+on|log\s*in\s+as)\b.{0,50}\b(?:account|password|login|session|database|server|users?|family|member|permission|sharing|privacy|security|app|someone|him|her)\b",
        r"\b(?:sql\s*injection|xss|csrf|session\s+hijack\w*|privilege\s+escalation|password\s+hash(?:es)?|exploit\s+(?:the\s+)?(?:app|server|api|database))\b",
        r"\b(?:reveal|show|print|tell|give|leak|repeat|display|dump|export|share)\b.{0,30}\b(?:system\s+prompt|your\s+(?:instructions|prompt|rules|configuration)|api[\s_-]?key|secret[\s_-]?key|data[\s_-]?key|\.env|ai_config|the\s+database|session\s+cookie)\b",
    ),
    INJECTION: _c(
        r"\b(?:ignore|disregard|forget|override|bypass|disable|turn\s+off)\b.{0,30}\b(?:previous|prior|above|earlier|all|any|your|the|safety|these|those)\b.{0,20}\b(?:instructions?|rules?|prompts?|guidelines?|restrictions?|filters?|safeguards?|guardrails?|policies)\b",
        r"\b(?:jailbreak|do\s+anything\s+now|developer\s+mode|dan\s+mode|god\s+mode)\b",
        r"\bpretend\b.{0,40}\b(?:no\s+(?:rules|restrictions|limits)|unrestricted|unfiltered|without\s+(?:rules|restrictions|limits))\b",
        r"\b(?:act|behave|respond)\s+as\s+(?:an?\s+)?(?:unrestricted|unfiltered|uncensored|evil)\b",
        r"\byou\s+are\s+no\s+longer\s+(?:bound|restricted|limited)\b",
    ),
}

# AI replies that must never reach the screen (instructions to hurt someone, lethal amounts).
_OUTPUT_RULES = _c(
    r"\b(?:lethal|fatal|deadly)\s+(?:dose|amount|quantity)\s+(?:of|is|would\s+be|for)\b",
    r"\b(?:to\s+)?(?:kill|poison|overdose)\s+(?:yourself|someone|him|her|them|a\s+person)\b",
    r"\b(?:here'?s|here\s+is|follow\s+these)\s+(?:how|steps?|a\s+way)\s+to\s+(?:poison|kill|harm|hurt|overdose|hack|break\s+into)\b",
    r"\b(?:my|the)\s+system\s+prompt\s+(?:is|says|reads)\b",
    r"\bapi[\s_-]?key\s+(?:is|=|:)\s*[A-Za-z0-9_\-]{16,}",
)

_REPLIES = {
    "abandoned": {
        "en": "This request has been abandoned. CareLens can't help with anything that could put you or another person at risk, or that tries to get around privacy and security. You can ask me about your own records, medicines or reminders instead.",
        "hi": "यह अनुरोध रद्द कर दिया गया है। CareLens ऐसी किसी भी चीज़ में मदद नहीं कर सकता जिससे आपको या किसी और को ख़तरा हो, या जो गोपनीयता और सुरक्षा को तोड़ने की कोशिश करे। आप अपने रिकॉर्ड, दवाइयों या रिमाइंडर के बारे में पूछ सकते हैं।",
        "kn": "ಈ ವಿನಂತಿಯನ್ನು ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ನಿಮಗೆ ಅಥವಾ ಬೇರೆಯವರಿಗೆ ಅಪಾಯ ತರಬಹುದಾದ, ಅಥವಾ ಗೌಪ್ಯತೆ ಮತ್ತು ಭದ್ರತೆಯನ್ನು ಮೀರಲು ಪ್ರಯತ್ನಿಸುವ ಯಾವುದಕ್ಕೂ CareLens ಸಹಾಯ ಮಾಡಲಾರದು. ನಿಮ್ಮ ದಾಖಲೆಗಳು, ಔಷಧಿಗಳು ಅಥವಾ ಜ್ಞಾಪನೆಗಳ ಬಗ್ಗೆ ಕೇಳಬಹುದು.",
        "ta": "இந்தக் கோரிக்கை நிறுத்தப்பட்டது. உங்களுக்கோ மற்றவர்களுக்கோ ஆபத்து ஏற்படுத்தக்கூடிய, அல்லது தனியுரிமை மற்றும் பாதுகாப்பை மீற முயலும் எதற்கும் CareLens உதவ முடியாது. உங்கள் பதிவுகள், மருந்துகள் அல்லது நினைவூட்டல்கள் பற்றி கேளுங்கள்.",
        "te": "ఈ అభ్యర్థన రద్దు చేయబడింది. మీకు లేదా ఇతరులకు ప్రమాదం కలిగించే, లేదా గోప్యత మరియు భద్రతను దాటవేయడానికి ప్రయత్నించే దేనికీ CareLens సహాయం చేయలేదు. మీ రికార్డులు, మందులు లేదా రిమైండర్ల గురించి అడగండి.",
        "ml": "ഈ അഭ്യർത്ഥന റദ്ദാക്കി. നിങ്ങൾക്കോ മറ്റുള്ളവർക്കോ അപകടമുണ്ടാക്കാവുന്ന, അല്ലെങ്കിൽ സ്വകാര്യതയും സുരക്ഷയും മറികടക്കാൻ ശ്രമിക്കുന്ന ഒന്നിനും CareLens സഹായിക്കില്ല. നിങ്ങളുടെ രേഖകൾ, മരുന്നുകൾ, ഓർമ്മപ്പെടുത്തലുകൾ എന്നിവയെക്കുറിച്ച് ചോദിക്കാം.",
        "mr": "ही विनंती रद्द करण्यात आली आहे. तुम्हाला किंवा इतरांना धोका होऊ शकेल, किंवा गोपनीयता व सुरक्षितता भंग करण्याचा प्रयत्न करेल अशा कोणत्याही गोष्टीसाठी CareLens मदत करू शकत नाही. तुम्ही तुमचे रेकॉर्ड, औषधे किंवा स्मरणपत्रे याबद्दल विचारू शकता.",
        "bn": "এই অনুরোধটি বাতিল করা হয়েছে। আপনার বা অন্য কারও ক্ষতি হতে পারে, কিংবা গোপনীয়তা ও নিরাপত্তা এড়ানোর চেষ্টা করে — এমন কিছুতে CareLens সাহায্য করতে পারে না। আপনি আপনার রেকর্ড, ওষুধ বা রিমাইন্ডার সম্পর্কে জিজ্ঞাসা করতে পারেন।",
    },
    # Someone who may be thinking of harming themselves gets a kind message and a real number, not a bare refusal.
    "support": {
        "en": "I'm really sorry you're feeling this way, and I'm glad you said it. I can't help with this request, so it has been abandoned. You don't have to go through this alone, so please talk to someone right now. In India you can call Tele-MANAS on 14416 (free, 24x7) or emergency services on 112. If you are elsewhere, call your local emergency number. If you can, ask a person you trust to stay with you.",
        "hi": "मुझे बहुत दुख है कि आप ऐसा महसूस कर रहे हैं, और मुझे खुशी है कि आपने बताया। मैं इस अनुरोध में मदद नहीं कर सकता, इसलिए इसे रद्द कर दिया गया है। आप अकेले नहीं हैं — कृपया अभी किसी से बात करें। भारत में आप Tele-MANAS को 14416 पर (मुफ़्त, 24x7) या आपातकालीन सेवा को 112 पर कॉल कर सकते हैं। हो सके तो किसी भरोसेमंद व्यक्ति को अपने पास बुला लें।",
        "kn": "ನೀವು ಹೀಗೆ ಅನುಭವಿಸುತ್ತಿರುವುದು ತಿಳಿದು ತುಂಬಾ ಬೇಸರವಾಗುತ್ತದೆ; ನೀವು ಹೇಳಿದ್ದು ಒಳ್ಳೆಯದು. ಈ ವಿನಂತಿಗೆ ನಾನು ಸಹಾಯ ಮಾಡಲಾರೆ, ಆದ್ದರಿಂದ ಅದನ್ನು ರದ್ದುಗೊಳಿಸಲಾಗಿದೆ. ನೀವು ಒಬ್ಬರೇ ಅಲ್ಲ — ದಯವಿಟ್ಟು ಈಗಲೇ ಯಾರೊಂದಿಗಾದರೂ ಮಾತನಾಡಿ. ಭಾರತದಲ್ಲಿ Tele-MANAS ಗೆ 14416 (ಉಚಿತ, 24x7) ಅಥವಾ ತುರ್ತು ಸೇವೆಗೆ 112 ಕರೆ ಮಾಡಬಹುದು. ಸಾಧ್ಯವಾದರೆ ನಂಬಿಕೆಯ ವ್ಯಕ್ತಿಯನ್ನು ನಿಮ್ಮ ಬಳಿ ಇರಲು ಕೇಳಿ.",
        "ta": "நீங்கள் இப்படி உணர்வதைக் கேட்டு வருந்துகிறேன்; சொன்னதற்கு நன்றி. இந்தக் கோரிக்கைக்கு என்னால் உதவ முடியாது, எனவே அது நிறுத்தப்பட்டது. நீங்கள் தனியாக இல்லை — தயவுசெய்து இப்போதே யாரிடமாவது பேசுங்கள். இந்தியாவில் Tele-MANAS 14416 (இலவசம், 24x7) அல்லது அவசர சேவை 112 ஐ அழைக்கலாம். முடிந்தால் நம்பிக்கையான ஒருவரை உங்களுடன் இருக்கச் சொல்லுங்கள்.",
        "te": "మీరు ఇలా భావిస్తున్నందుకు చాలా బాధగా ఉంది; చెప్పినందుకు సంతోషం. ఈ అభ్యర్థనకు నేను సహాయం చేయలేను, కాబట్టి అది రద్దు చేయబడింది. మీరు ఒంటరివారు కారు — దయచేసి ఇప్పుడే ఎవరితోనైనా మాట్లాడండి. భారతదేశంలో Tele-MANAS 14416 (ఉచితం, 24x7) లేదా అత్యవసర సేవ 112 కు కాల్ చేయవచ్చు. వీలైతే నమ్మకమైన వ్యక్తిని మీ దగ్గర ఉండమని అడగండి.",
        "ml": "നിങ്ങൾക്ക് ഇങ്ങനെ തോന്നുന്നതിൽ എനിക്ക് വളരെ വിഷമമുണ്ട്; പറഞ്ഞതിൽ സന്തോഷം. ഈ അഭ്യർത്ഥനയിൽ എനിക്ക് സഹായിക്കാൻ കഴിയില്ല, അതിനാൽ അത് റദ്ദാക്കി. നിങ്ങൾ ഒറ്റയ്ക്കല്ല — ദയവായി ഇപ്പോൾ തന്നെ ആരോടെങ്കിലും സംസാരിക്കൂ. ഇന്ത്യയിൽ Tele-MANAS 14416 (സൗജന്യം, 24x7) അല്ലെങ്കിൽ അടിയന്തര സേവനം 112 വിളിക്കാം. കഴിയുമെങ്കിൽ വിശ്വസ്തനായ ഒരാളോട് കൂടെ ഇരിക്കാൻ പറയൂ.",
        "mr": "तुम्हाला असे वाटत आहे हे ऐकून मला खूप वाईट वाटले; तुम्ही सांगितले हे चांगले केले. या विनंतीसाठी मी मदत करू शकत नाही, म्हणून ती रद्द करण्यात आली आहे. तुम्ही एकटे नाही — कृपया आत्ताच कोणाशी तरी बोला. भारतात Tele-MANAS ला 14416 (मोफत, 24x7) किंवा आपत्कालीन सेवेला 112 वर कॉल करू शकता. शक्य असल्यास विश्वासू व्यक्तीला तुमच्याजवळ थांबायला सांगा.",
        "bn": "আপনি এমন অনুভব করছেন শুনে আমি খুব দুঃখিত; বলেছেন বলে ভালো লাগল। এই অনুরোধে আমি সাহায্য করতে পারব না, তাই এটি বাতিল করা হয়েছে। আপনি একা নন — অনুগ্রহ করে এখনই কারও সাথে কথা বলুন। ভারতে Tele-MANAS 14416 (বিনামূল্যে, 24x7) বা জরুরি পরিষেবা 112 এ কল করতে পারেন। পারলে বিশ্বস্ত কাউকে আপনার কাছে থাকতে বলুন।",
    },
}


class Verdict(NamedTuple):
    blocked: bool
    category: Optional[str] = None
    reply: Optional[str] = None


ALLOWED = Verdict(False)


def reply_for(category, language="en"):
    kind = "support" if category == SELF_HARM else "abandoned"
    table = _REPLIES[kind]
    return table.get(language) or table["en"]


def screen_input(text, language="en"):
    """Decide whether text typed to the assistant may be answered. Returns a Verdict."""
    forms = _variants(text)
    if not forms[0]:
        return ALLOWED
    # Self-harm is checked first: it needs the kinder message even if other rules also match.
    for category in (SELF_HARM, HARM_OTHERS, PRIVACY, INJECTION):
        if any(rx.search(t) for rx in _RULES[category] for t in forms):
            return Verdict(True, category, reply_for(category, language))
    return ALLOWED


def screen_output(text, language="en"):
    """Last check on what the AI wrote. A harmful reply is replaced, never shown."""
    if any(rx.search(t) for rx in _OUTPUT_RULES for t in _variants(text)):
        return Verdict(True, "unsafe_output", reply_for("unsafe_output", language))
    return ALLOWED


def looks_like_injection(text):
    """True if stored text (e.g. a document someone shared) tries to give the assistant orders."""
    return any(rx.search(t) for rx in _RULES[INJECTION] for t in _variants(text[:20000]))


_TAGS = re.compile(r"<\s*/?\s*(context|system|assistant|instructions?)\s*>", re.I)


def neutralise_context(text):
    """Stored text (documents, notes) is data. Remove markers that could be read as the end of the data block."""
    return _TAGS.sub(lambda m: "[" + m.group(1) + "]", text or "")


# ---------- privacy: data minimisation for the cloud AI provider ----------
# Direct identifiers are removed from the COPY of the text that is sent to the AI provider. Stored records are never changed.
_REDACTIONS = [
    ("CARD", re.compile(r"(?<![\d.])\d(?:[ -]?\d){12,18}(?![\d.])")),
    ("EMAIL", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    ("AADHAAR", re.compile(r"(?<![\d.])\d{4}[ -]\d{4}[ -]\d{4}(?![\d.])")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?<![\d.])(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}(?![\d.])")),
    ("PHONE", re.compile(r"(?<![\d.])\+\d{1,3}[ -]?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]?\d{3,4}(?![\d.])")),
]


def redact_identifiers(text):
    """Replace emails, phone numbers, Aadhaar/PAN-style IDs and card-like numbers with placeholders."""
    if not isinstance(text, str) or not text:
        return text
    for label, pattern in _REDACTIONS:
        text = pattern.sub(f"[{label} REMOVED]", text)
    return text
