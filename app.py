
import streamlit as st
import requests
import json
import re

# ==================================================
# CONFIGURATION
# ==================================================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:1b"

st.set_page_config(
    page_title="AI Notes Explainer",
    page_icon="📘",
    layout="centered"
)

# ==================================================
# SESSION STATE
# ==================================================

defaults = {
    "quiz": [],
    "submitted": False,
    "answers": {},
    "quiz_topic_display": "",
    "explanation_result": None,
    "explanation_topic": ""
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ==================================================
# OLLAMA AI FUNCTION
# ==================================================

def ask_ai(prompt):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": 2500
            }
        },
        timeout=300
    )

    response.raise_for_status()
    result = response.json().get("response", "")
    return json.loads(result)


# ==================================================
# EXPLAIN TOPIC
# ==================================================

def explain_topic(topic):
    prompt = f"""
Explain the following topic in simple English for a beginner.

TOPIC:
{topic}

Return valid JSON with these fields:
{{
  "title": "Short title",
  "definition": "Simple definition",
  "how_it_works": "Explanation",
  "example": "One example",
  "key_points": ["Point 1", "Point 2", "Point 3", "Point 4"],
  "summary": "Short summary"
}}

Use accurate information and simple language.
"""

    return ask_ai(prompt)


# ==================================================
# GENERATE AND VALIDATE QUIZ
# ==================================================

def generate_quiz(topic, count):
    prompt = f"""
Create exactly {count} multiple-choice questions about the main
subject in the following input.

USER INPUT:
{topic}

RULES:
1. Identify the main subject, even if the input is a long paragraph.
2. Create questions about that subject.
3. Use factual, clear questions suitable for beginners.
4. Each question must have exactly four distinct options.
5. Exactly one option must be correct.
6. The field "correct_answer" MUST contain the complete exact text
   of one of the four options.
7. Copy the correct option exactly into "correct_answer".
8. Never guess the answer.
9. Avoid ambiguous questions.
10. For movie questions, use established facts about the films.
11. Include a short explanation supporting the correct answer.
12. Do not repeat questions.

Return ONLY valid JSON in this structure:

{{
  "topic_title": "Short subject title",
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "correct_answer": "Exact text of the correct option",
      "explanation": "Why the answer is correct"
    }}
  ]
}}

Generate exactly {count} questions.
"""

    data = ask_ai(prompt)

    raw_questions = data.get("questions", [])
    title = data.get("topic_title", "")

    if not isinstance(raw_questions, list):
        raise ValueError("The AI did not return a valid question list.")

    validated = []
    seen = set()

    for item in raw_questions:
        if not isinstance(item, dict):
            continue

        question = item.get("question")
        options = item.get("options")
        correct_answer = item.get("correct_answer")
        explanation = item.get("explanation", "")

        if not isinstance(question, str) or not question.strip():
            continue

        if not isinstance(options, list) or len(options) != 4:
            continue

        if not all(isinstance(option, str) for option in options):
            continue

        options = [option.strip() for option in options]

        if any(not option for option in options):
            continue

        # Reject duplicate options.
        if len(set(option.casefold() for option in options)) != 4:
            continue

        if not isinstance(correct_answer, str):
            continue

        # Find the correct option by its exact text, not a model-generated
        # numerical index.
        matching_options = [
            option for option in options
            if option.casefold() == correct_answer.strip().casefold()
        ]

        if len(matching_options) != 1:
            continue

        correct_answer = matching_options[0]
        correct_index = options.index(correct_answer)

        question_key = question.strip().casefold()

        if question_key in seen:
            continue

        seen.add(question_key)

        validated.append({
            "question": question.strip(),
            "options": options,
            "answer": correct_index,
            "correct_answer": correct_answer,
            "explanation": (
                explanation if isinstance(explanation, str) else ""
            )
        })

    if len(validated) < count:
        raise ValueError(
            f"The AI returned only {len(validated)} valid questions. "
            "Please click Generate Quiz again."
        )

    if not isinstance(title, str) or not title.strip():
        title = topic.strip()[:60]

    return validated[:count], title.strip()


# ==================================================
# HEADER
# ==================================================

st.title("📘 AI Notes Explainer")
st.write("Enter any topic to learn or generate a quiz.")
st.caption("Powered by your free local Ollama AI model.")

explain_tab, quiz_tab = st.tabs(
    ["📖 Explain Topic", "📝 Generate Quiz"]
)


# ==================================================
# TAB 1: EXPLAIN TOPIC
# ==================================================

with explain_tab:
    st.subheader("Understand Any Topic")

    explanation_input = st.text_area(
        "Enter a topic or paste your notes",
        placeholder="Example: Tsunami, The Avengers, RAG",
        height=120,
        key="explanation_input"
    )

    if st.button("Explain Topic", key="explain_button"):
        if not explanation_input.strip():
            st.warning("Please enter a topic.")

        else:
            try:
                with st.spinner("Preparing explanation..."):
                    result = explain_topic(explanation_input.strip())

                st.session_state.explanation_result = result
                st.session_state.explanation_topic = explanation_input.strip()

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to Ollama. Check that Ollama is running.")

            except Exception as error:
                st.error(f"Explanation failed: {error}")

    if st.session_state.explanation_result:
        result = st.session_state.explanation_result

        st.markdown(f"### {result.get('title', 'Explanation')}")

        st.markdown("#### Definition")
        st.write(result.get("definition", ""))

        st.markdown("#### How It Works")
        st.write(result.get("how_it_works", ""))

        st.markdown("#### Example")
        st.write(result.get("example", ""))

        st.markdown("#### Key Points")
        points = result.get("key_points", [])

        if isinstance(points, list):
            for point in points:
                st.markdown(f"- {point}")

        st.markdown("#### Summary")
        st.write(result.get("summary", ""))


# ==================================================
# TAB 2: GENERATE QUIZ
# ==================================================

with quiz_tab:
    st.subheader("Generate Questions on Any Topic")

    topic_input = st.text_area(
        "Enter any topic or paste a description",
        placeholder="Example: The Avengers is a superhero movie series...",
        height=150,
        key="quiz_topic"
    )

    question_count = st.selectbox(
        "Number of questions",
        [5, 10],
        key="question_count"
    )

    if st.button("Generate Quiz", key="generate_quiz_button"):
        topic = topic_input.strip()

        if not topic:
            st.warning("Please enter a topic or description.")

        else:
            try:
                with st.spinner("Generating your quiz..."):
                    new_quiz, short_title = generate_quiz(
                        topic, question_count
                    )

                st.session_state.quiz = new_quiz
                st.session_state.quiz_topic_display = short_title
                st.session_state.answers = {}
                st.session_state.submitted = False

                st.success("Quiz generated successfully!")

            except requests.exceptions.ConnectionError:
                st.error(
                    "Cannot connect to Ollama. Open a terminal and run "
                    "'ollama serve' if Ollama is not already running."
                )

            except requests.exceptions.Timeout:
                st.error("The AI took too long. Please try again.")

            except Exception as error:
                st.error(f"Quiz generation failed: {error}")

    # --------------------------------------------------
    # DISPLAY QUIZ
    # --------------------------------------------------

    if st.session_state.quiz:
        quiz = st.session_state.quiz

        st.divider()
        st.subheader(f"Quiz: {st.session_state.quiz_topic_display}")

        with st.form("quiz_answer_form"):
            selected_answers = {}

            for i, question in enumerate(quiz):
                st.markdown(
                    f"**Q{i + 1}. {question['question']}**"
                )

                selected_answers[i] = st.radio(
                    f"Choose an answer for question {i + 1}",
                    question["options"],
                    index=None,
                    key=f"quiz_answer_{i}",
                    label_visibility="collapsed"
                )

                st.write("")

            submitted = st.form_submit_button("Submit Answers")

        if submitted:
            st.session_state.answers = selected_answers
            st.session_state.submitted = True

        # --------------------------------------------------
        # SCORE AND REVIEW
        # --------------------------------------------------

        if st.session_state.submitted:
            answers = st.session_state.answers

            score = 0
            unanswered = 0

            for i, question in enumerate(quiz):
                selected = answers.get(i)

                if selected is None:
                    unanswered += 1
                elif selected == question["correct_answer"]:
                    score += 1

            total = len(quiz)
            incorrect = total - score - unanswered
            percentage = round(score / total * 100)

            st.divider()
            st.subheader("📊 Your Results")

            st.metric("Your Score", f"{score} / {total}")
            st.write(f"Correct answers: {score}")
            st.write(f"Incorrect answers: {incorrect}")
            st.write(f"Unanswered questions: {unanswered}")

            st.progress(percentage)
            st.write(f"Percentage: {percentage}%")

            st.markdown("### Review Your Answers")

            for i, question in enumerate(quiz):
                selected = answers.get(i)
                correct = question["correct_answer"]

                st.markdown(
                    f"**Q{i + 1}. {question['question']}**"
                )

                if selected == correct:
                    st.success(f"Correct! {correct}")

                else:
                    st.error(
                        "Your answer: "
                        + (selected if selected is not None else "Not answered")
                    )
                    st.info(f"Correct answer: {correct}")

                st.write(
                    "Explanation: "
                    + question.get("explanation", "")
                )

            if st.button("Generate Another Quiz", key="another_quiz"):
                st.session_state.quiz = []
                st.session_state.answers = {}
                st.session_state.submitted = False
                st.session_state.quiz_topic_display = ""
                st.rerun()
