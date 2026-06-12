from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Question:
    question_id: str
    exam_type: str
    section: str
    question_type: str
    difficulty: str
    stem: str
    options: list[str]
    answer: str
    explanation: str
    tags: list[str] = field(default_factory=list)
    estimated_time_seconds: int = 60
    passage: Optional[str] = None


MOCK_QUESTIONS: list[dict] = [
    {
        "question_id": "cet6_reading_001",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "The concept of sustainability has gained significant traction in recent years, "
            "moving from a niche environmental concern to a mainstream business imperative. "
            "Companies are increasingly recognizing that long-term profitability is intrinsically "
            "linked to sustainable practices. However, the path to genuine sustainability is "
            "fraught with challenges, including greenwashing, short-term profit pressures, and "
            "the complexity of measuring environmental impact across global supply chains."
        ),
        "stem": (
            "What is the main challenge to achieving genuine sustainability according to the passage?"
        ),
        "options": [
            "A) Lack of environmental regulations",
            "B) Greenwashing and short-term profit pressures",
            "C) Insufficient technological development",
            "D) Low consumer awareness",
        ],
        "answer": "B",
        "explanation": (
            "The passage explicitly states the path to genuine sustainability is 'fraught with "
            "challenges, including greenwashing, short-term profit pressures, and the complexity "
            "of measuring environmental impact.'"
        ),
        "tags": ["sustainability", "reading comprehension", "main idea"],
        "estimated_time_seconds": 120,
    },
    {
        "question_id": "cet6_reading_002",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "Emotional intelligence, often abbreviated as EQ, has emerged as a critical factor "
            "in workplace success, sometimes surpassing traditional IQ in predictive validity. "
            "Individuals with high EQ demonstrate superior abilities in navigating interpersonal "
            "dynamics, managing stress, and leading teams effectively. Research indicates that "
            "while IQ may help someone get hired, EQ is what enables them to advance and thrive "
            "in their career over the long term."
        ),
        "stem": (
            "According to the passage, what role does emotional intelligence play in career development?"
        ),
        "options": [
            "A) It is less important than IQ for getting hired",
            "B) It helps individuals advance and thrive long-term",
            "C) It only matters for leadership positions",
            "D) It has no effect on workplace success",
        ],
        "answer": "B",
        "explanation": (
            "The passage states that 'EQ is what enables them to advance and thrive in their "
            "career over the long term,' directly supporting answer B."
        ),
        "tags": ["emotional intelligence", "EQ", "career"],
        "estimated_time_seconds": 120,
    },
    {
        "question_id": "cet6_reading_003",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "hard",
        "passage": (
            "The phenomenon of 'digital hoarding' — the accumulation of digital files, photos, "
            "and messages to the point of overwhelming storage capacity — mirrors traditional "
            "hoarding behavior but presents unique challenges. Unlike physical hoarding, digital "
            "hoarding is largely invisible, allowing individuals to accumulate thousands of files "
            "without social stigma. However, research suggests that this behavior can lead to "
            "increased anxiety, reduced productivity, and difficulty making decisions about what "
            "to keep and what to discard."
        ),
        "stem": (
            "What makes digital hoarding different from physical hoarding according to the passage?"
        ),
        "options": [
            "A) It causes less anxiety than physical hoarding",
            "B) It is largely invisible and carries no social stigma",
            "C) It only affects people over 40",
            "D) It is easier to manage than physical hoarding",
        ],
        "answer": "B",
        "explanation": (
            "The passage states that 'Unlike physical hoarding, digital hoarding is largely "
            "invisible, allowing individuals to accumulate thousands of files without social stigma.'"
        ),
        "tags": ["digital hoarding", "comparison", "detail"],
        "estimated_time_seconds": 150,
    },
    {
        "question_id": "cet4_reading_001",
        "exam_type": "CET-4",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "easy",
        "passage": (
            "Regular exercise has been shown to have numerous health benefits, including "
            "reduced risk of heart disease, improved mental health, and better sleep quality. "
            "Experts recommend at least 150 minutes of moderate aerobic activity per week, "
            "which can be broken down into 30-minute sessions five days a week. Even small "
            "amounts of physical activity can make a difference, and the best exercise is "
            "one that you enjoy and will stick with over time."
        ),
        "stem": ("How much moderate aerobic activity do experts recommend per week?"),
        "options": [
            "A) 60 minutes",
            "B) 100 minutes",
            "C) 150 minutes",
            "D) 200 minutes",
        ],
        "answer": "C",
        "explanation": (
            "The passage clearly states that 'Experts recommend at least 150 minutes of "
            "moderate aerobic activity per week.'"
        ),
        "tags": ["health", "exercise", "detail"],
        "estimated_time_seconds": 90,
    },
    {
        "question_id": "cet4_reading_002",
        "exam_type": "CET-4",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "easy",
        "passage": (
            "Learning a new language as an adult can be challenging, but research shows that "
            "it is never too late to start. Studies have found that adults often learn grammar "
            "and vocabulary more quickly than children, although children may have an advantage "
            "in pronunciation. The key to successful language learning at any age is consistent "
            "practice and exposure to the language through reading, listening, and speaking."
        ),
        "stem": ("What advantage do children have over adults in language learning?"),
        "options": [
            "A) Learning grammar faster",
            "B) Better vocabulary acquisition",
            "C) Better pronunciation",
            "D) More motivation to learn",
        ],
        "answer": "C",
        "explanation": (
            "The passage states that 'children may have an advantage in pronunciation,' "
            "directly supporting answer C."
        ),
        "tags": ["language learning", "comparison", "detail"],
        "estimated_time_seconds": 90,
    },
    {
        "question_id": "cet4_reading_003",
        "exam_type": "CET-4",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "The rise of remote work has transformed the traditional office environment. "
            "While many employees enjoy the flexibility and improved work-life balance that "
            "comes with working from home, employers face new challenges in maintaining "
            "team cohesion and productivity. Studies show that remote workers can be just "
            "as productive as office workers, but effective communication and clear expectations "
            "are essential for success."
        ),
        "stem": ("What challenge do employers face with remote work according to the passage?"),
        "options": [
            "A) Higher office costs",
            "B) Maintaining team cohesion and productivity",
            "C) Finding qualified workers",
            "D) Managing employee schedules",
        ],
        "answer": "B",
        "explanation": (
            "The passage states that 'employers face new challenges in maintaining "
            "team cohesion and productivity.'"
        ),
        "tags": ["remote work", "main idea", "workplace"],
        "estimated_time_seconds": 100,
    },
    {
        "question_id": "cet6_reading_004",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "hard",
        "passage": (
            "Artificial intelligence is increasingly being used in healthcare, from diagnosing "
            "diseases to personalizing treatment plans. While AI systems can process vast amounts "
            "of data and identify patterns that humans might miss, they also raise significant "
            "ethical concerns. These include issues of data privacy, algorithmic bias, and the "
            "potential displacement of healthcare workers. The challenge lies in harnessing "
            "AI's benefits while addressing these legitimate concerns."
        ),
        "stem": ("What is the main concern about AI in healthcare mentioned in the passage?"),
        "options": [
            "A) AI is too expensive to implement",
            "B) AI cannot process enough data",
            "C) Ethical concerns including privacy and bias",
            "D) AI is slower than human doctors",
        ],
        "answer": "C",
        "explanation": (
            "The passage mentions 'significant ethical concerns' including 'data privacy, "
            "algorithmic bias, and the potential displacement of healthcare workers.'"
        ),
        "tags": ["AI", "healthcare", "ethics", "main idea"],
        "estimated_time_seconds": 150,
    },
    {
        "question_id": "cet6_reading_005",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "Urbanization is transforming societies at an unprecedented rate. By 2050, it is "
            "estimated that nearly 70% of the world's population will live in cities. This "
            "rapid growth presents both opportunities and challenges. Cities offer better "
            "access to education, healthcare, and employment, but they also face issues "
            "such as overcrowding, pollution, and strain on infrastructure. Sustainable "
            "urban planning is essential to ensure that cities remain livable."
        ),
        "stem": (
            "What percentage of the world's population is expected to live in cities by 2050?"
        ),
        "options": [
            "A) 50%",
            "B) 60%",
            "C) 70%",
            "D) 80%",
        ],
        "answer": "C",
        "explanation": (
            "The passage states that 'it is estimated that nearly 70% of the world's "
            "population will live in cities' by 2050."
        ),
        "tags": ["urbanization", "statistics", "detail"],
        "estimated_time_seconds": 100,
    },
    {
        "question_id": "cet4_reading_004",
        "exam_type": "CET-4",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "The gig economy has changed how many people work. Instead of traditional "
            "full-time employment, millions of workers now take on short-term contracts "
            "or freelance jobs. This flexibility allows people to work when and where they "
            "choose, but it also means less job security and fewer benefits such as health "
            "insurance and retirement plans. The debate continues over whether the gig "
            "economy empowers workers or exploits them."
        ),
        "stem": (
            "What is one disadvantage of working in the gig economy mentioned in the passage?"
        ),
        "options": [
            "A) Limited work flexibility",
            "B) Lower pay for all jobs",
            "C) Less job security and fewer benefits",
            "D) Difficulty finding work",
        ],
        "answer": "C",
        "explanation": (
            "The passage states that gig work 'means less job security and fewer benefits "
            "such as health insurance and retirement plans.'"
        ),
        "tags": ["gig economy", "disadvantage", "detail"],
        "estimated_time_seconds": 100,
    },
    {
        "question_id": "cet4_reading_005",
        "exam_type": "CET-4",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "easy",
        "passage": (
            "Reading for pleasure has been linked to improved vocabulary, better writing skills, "
            "and increased empathy. Despite these benefits, surveys show that leisure reading "
            "has declined significantly over the past decade, particularly among young adults. "
            "The rise of social media and streaming services has been blamed for competing "
            "with books for people's attention. However, experts believe that encouraging "
            "reading habits early in life can help reverse this trend."
        ),
        "stem": ("What has been blamed for the decline in leisure reading?"),
        "options": [
            "A) Lack of good books",
            "B) High cost of books",
            "C) Social media and streaming services",
            "D) Decreased literacy rates",
        ],
        "answer": "C",
        "explanation": (
            "The passage states that 'The rise of social media and streaming services has "
            "been blamed for competing with books for people's attention.'"
        ),
        "tags": ["reading", "cause", "detail"],
        "estimated_time_seconds": 90,
    },
    {
        "question_id": "cet6_reading_006",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "hard",
        "passage": (
            "The concept of 'flow state' — a mental state of complete immersion in an activity — "
            "has been studied extensively by psychologists. When in flow, people experience "
            "heightened focus, enjoyment, and a sense of time passing quickly. Research shows "
            "that flow states are more likely to occur when the challenge level of a task "
            "matches the individual's skill level. Too easy, and boredom sets in; too difficult, "
            "and anxiety takes over."
        ),
        "stem": ("When are people most likely to experience a flow state?"),
        "options": [
            "A) When tasks are very easy",
            "B) When tasks are extremely difficult",
            "C) When challenge matches skill level",
            "D) When working alone",
        ],
        "answer": "C",
        "explanation": (
            "The passage states that 'flow states are more likely to occur when the challenge "
            "level of a task matches the individual's skill level.'"
        ),
        "tags": ["flow state", "psychology", "inference"],
        "estimated_time_seconds": 150,
    },
    {
        "question_id": "cet6_reading_007",
        "exam_type": "CET-6",
        "section": "reading comprehension",
        "question_type": "multiple_choice",
        "difficulty": "medium",
        "passage": (
            "Bilingual individuals often demonstrate cognitive advantages over monolinguals. "
            "Studies have shown that speaking two or more languages can improve memory, "
            "enhance problem-solving abilities, and even delay the onset of dementia. "
            "These benefits appear to stem from the constant mental exercise of switching "
            "between languages, which strengthens executive function and cognitive flexibility."
        ),
        "stem": ("What cognitive benefit do bilingual individuals often demonstrate?"),
        "options": [
            "A) Better physical coordination",
            "B) Improved memory and problem-solving",
            "C) Enhanced mathematical skills",
            "D) Increased artistic ability",
        ],
        "answer": "B",
        "explanation": (
            "The passage states that speaking two or more languages 'can improve memory, "
            "enhance problem-solving abilities, and even delay the onset of dementia.'"
        ),
        "tags": ["bilingual", "cognition", "detail"],
        "estimated_time_seconds": 120,
    },
    {
        "question_id": "cet4_writing_001",
        "exam_type": "CET-4",
        "section": "writing",
        "question_type": "essay_prompt",
        "difficulty": "medium",
        "passage": None,
        "stem": (
            "For this part, you are allowed 30 minutes to write a short essay on the topic: "
            "'The Importance of Learning a Foreign Language.' You should write at least 120 words "
            "but no more than 180 words."
        ),
        "options": [],
        "answer": "",
        "explanation": "",
        "tags": ["writing", "essay", "language learning"],
        "estimated_time_seconds": 1800,
    },
    {
        "question_id": "cet6_writing_001",
        "exam_type": "CET-6",
        "section": "writing",
        "question_type": "essay_prompt",
        "difficulty": "hard",
        "passage": None,
        "stem": (
            "For this part, you are allowed 30 minutes to write a short essay commenting on "
            "the saying 'The best way to predict the future is to create it.' You should write "
            "at least 150 words but no more than 200 words."
        ),
        "options": [],
        "answer": "",
        "explanation": "",
        "tags": ["writing", "essay", "proverb"],
        "estimated_time_seconds": 1800,
    },
]


class QuestionBank:
    """Local question bank for CET exam practice."""

    def __init__(self) -> None:
        self._questions = MOCK_QUESTIONS

    def get_question(self, question_id: str) -> Optional[Question]:
        for q in self._questions:
            if q["question_id"] == question_id:
                return Question(**q)
        return None

    def get_questions(
        self,
        exam_type: Optional[str] = None,
        section: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 10,
    ) -> list[Question]:
        filtered = self._questions
        if exam_type:
            filtered = [q for q in filtered if q["exam_type"] == exam_type]
        if section:
            filtered = [q for q in filtered if q["section"] == section]
        if difficulty:
            filtered = [q for q in filtered if q["difficulty"] == difficulty]
        return [Question(**q) for q in filtered[:limit]]


question_bank = QuestionBank()
