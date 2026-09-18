<!DOCTYPE html>
<html lang="uz">
<head>
    {% load static %}
    <meta charset="UTF-8">
    <title>AvtoIbrat - Test</title>

    <link rel="shortcut icon" href="{% static 'sinov_test_panel/favicon.png' %}">
    <link rel="stylesheet" href="{% static 'sinov_test_panel/style.css' %}">
</head>
<body>

<!-- ================= TOP BAR ================= -->
<div class="top-bar">
    <img src="{% static 'sinov_test_panel/logo.png' %}" class="logo" alt="Logo">
    {{ request.user.get_full_name }}
</div>

<!-- ================= QUESTION ================= -->
<div class="question-bar" id="questionText"></div>

<div class="wrapper">
    <div class="left" id="answers"></div>
    <div class="right" id="questionImage"></div>
</div>

<!-- ================= MODAL ================= -->
<div id="answerModal" class="modal-answer">
    <div class="modal-content-answer">
        <h3 id="modalTitle">—</h3>
        <div class="ans-buttons">
            <button onclick="closeModal()">Bekor qilish</button>
            <button onclick="confirmAnswer()">Tasdiqlash</button>
        </div>
    </div>
</div>

<script>
const sessionId = {{ session.id }};
const questions = {{ questions|safe }};

let index = 0;
let selectedAnswer = null;
let selectedBtn = null;

/* ================= RENDER QUESTION ================= */
function renderQuestion() {
    const q = questions[index];

    document.getElementById("questionText").innerText = q.text;

    const answersDiv = document.getElementById("answers");
    answersDiv.innerHTML = "";

    q.answers.forEach((a, i) => {
        answersDiv.innerHTML += `
        <div class="answer-row">
            <span class="key">F${i + 1}</span>
            <button
                class="ans-btn"
                data-correct="${a.is_correct ? '1' : '0'}"
                onclick="selectAnswer(${a.id}, \`${a.text}\`, this)">
                ${a.text}
            </button>
        </div>`;
    });

    document.getElementById("questionImage").innerHTML =
        q.image ? `<img src="${q.image}">` : "";
}

/* ================= SELECT ANSWER ================= */
function selectAnswer(id, text, btn) {
    selectedAnswer = id;
    selectedBtn = btn;
    answersState[index] = "pending"; // 🟡
    renderNumbers();
    document.getElementById("modalTitle").innerText = text;
    document.getElementById("answerModal").style.display = "flex";
}

/* ================= CLOSE MODAL ================= */
function closeModal() {
    document.getElementById("answerModal").style.display = "none";
}

/* ================= CONFIRM ANSWER ================= */
function confirmAnswer() {

    // eski ranglarni tozalash
    document.querySelectorAll(".ans-btn")
        .forEach(b => b.classList.remove("correct", "wrong"));

    // ❗ ASOSIY VA TO‘G‘RI TEKSHIRUV
    const isCorrect = selectedBtn.dataset.correct === "1";

    // rang berish
    selectedBtn.classList.add(isCorrect ? "correct" : "wrong");

    // backendga yuborish
    fetch("{% url 'submit_answer' %}", {
        method: "POST",
        headers: {
            "X-CSRFToken": "{{ csrf_token }}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        body: new URLSearchParams({
            session_id: sessionId,
            question_id: questions[index].id,
            answer_id: selectedAnswer
        })
    });

    closeModal();

    // keyingi savol
    setTimeout(() => {
        index++;
        if (index >= questions.length) {
            window.location.href = "/test-finish/" + sessionId;
        } else {
            renderQuestion();
        }
    }, 600);
}

/* ================= START ================= */
renderQuestion();

</script>

</body>
</html>
