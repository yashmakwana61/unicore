/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class TakeQuizClientAction extends Component {
    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            quizzes: [],
            selectedQuiz: null,
            questions: [],
            answers: {},
            tabSwitches: 0,
            status: 'list', // 'list', 'taking', 'submitted'
            timeRemaining: 0,
            attemptId: null
        });
        
        this.timer = null;
        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);

        onWillStart(async () => {
            await this.loadQuizzes();
        });
        
        onMounted(() => {
            document.addEventListener("visibilitychange", this.handleVisibilityChange);
        });
        
        onWillUnmount(() => {
            document.removeEventListener("visibilitychange", this.handleVisibilityChange);
            this.clearTimer();
        });
    }
    
    async loadQuizzes() {
        // Fetch active quizzes
        this.state.quizzes = await this.orm.searchRead(
            "unicore.quiz",
            [["state", "=", "active"]],
            ["title", "time_limit"]
        );
    }
    
    async startQuiz(quizId) {
        try {
            // First find the student record for the current user
            const students = await this.orm.searchRead(
                "unicore.student",
                [],
                ["id"],
                { limit: 1 }
            );
            
            if (students.length === 0) {
                this.notification.add("You must be registered as a student to take a quiz.", { type: "danger" });
                return;
            }
            
            const studentId = students[0].id;
            
            // Create a quiz attempt
            const attemptIds = await this.orm.create("unicore.quiz.attempt", [{
                student_id: studentId,
                quiz_id: quizId,
                state: 'in_progress'
            }]);
            
            this.state.attemptId = attemptIds[0];
            
            // Fetch the quiz details including questions
            const quizData = await this.orm.read("unicore.quiz", [quizId], ["title", "time_limit", "question_ids"]);
            const quiz = quizData[0];
            this.state.selectedQuiz = quiz;
            
            // Fetch questions
            this.state.questions = await this.orm.read("unicore.question.bank", quiz.question_ids, [
                "question_text", "option_a", "option_b", "option_c", "option_d"
            ]);
            
            // Initialize answers
            this.state.answers = {};
            this.state.tabSwitches = 0;
            this.state.status = 'taking';
            this.state.timeRemaining = quiz.time_limit * 60; // in seconds
            
            this.startTimer();
        } catch (error) {
            this.notification.add(error.message || "Failed to start quiz. You may have already attempted this quiz.", { type: "danger" });
        }
    }
    
    startTimer() {
        this.clearTimer();
        this.timer = setInterval(() => {
            if (this.state.timeRemaining > 0) {
                this.state.timeRemaining--;
            } else {
                this.submitQuiz();
            }
        }, 1000);
    }
    
    clearTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }
    
    formatTime(seconds) {
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = (seconds % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }
    
    handleVisibilityChange() {
        if (this.state.status === 'taking' && document.hidden) {
            this.state.tabSwitches++;
            this.notification.add("Warning: You switched tabs! This has been recorded.", { type: "warning" });
        }
    }
    
    setAnswer(questionId, option) {
        this.state.answers[questionId] = option;
    }
    
    async submitQuiz() {
        this.clearTimer();
        
        try {
            await this.orm.call("unicore.quiz.attempt", "submit_quiz_attempt", [
                this.state.attemptId,
                this.state.answers,
                this.state.tabSwitches
            ]);
            
            this.state.status = 'submitted';
            this.notification.add("Quiz submitted successfully!", { type: "success" });
        } catch (error) {
            this.notification.add("Failed to submit quiz.", { type: "danger" });
        }
    }
    
    goBack() {
        this.state.status = 'list';
        this.state.selectedQuiz = null;
        this.loadQuizzes();
    }
}

TakeQuizClientAction.template = "unicore_quiz.TakeQuizClientAction";

registry.category("actions").add("unicore_quiz.take_quiz_client_action", TakeQuizClientAction);
