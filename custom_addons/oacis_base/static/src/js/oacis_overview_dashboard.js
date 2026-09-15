/** @odoo-module **/

import { Component, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class OacisOverviewDashboard extends Component {
    static template = "oacis_base.OacisOverviewDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            data: null,
            loading: true,
            error: null,
            filters: {
                company_id: null,
                campus_id: null,
            },
            companies: [],
            campuses: [],
        });
        this.chartInstances = {};
        onMounted(() => {
            this.loadCompaniesAndCampuses().then(() => this.loadDashboardData());
        });
    }

    async loadCompaniesAndCampuses() {
        try {
            const companies = await this.orm.searchRead("res.company", [], ["id", "name"]);
            this.state.companies = companies || [];
            const campuses = await this.orm.searchRead("oacis.campus", [], ["id", "campus_display_name", "name"]);
            this.state.campuses = campuses || [];
        } catch (e) {
            // ignore
        }
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const company_id = this.state.filters.company_id ? parseInt(this.state.filters.company_id) : null;
            const campus_id = this.state.filters.campus_id ? parseInt(this.state.filters.campus_id) : null;
            const data = await this.orm.call("oacis.overview.dashboard", "get_overview_data", [], {
                company_id: company_id,
                campus_id: campus_id,
            });
            this.state.data = data;
            this.state.loading = false;
            setTimeout(() => this._renderCharts(), 100);
        } catch (error) {
            this.state.error = error.message || "Failed to load overview data";
            this.state.loading = false;
            this.notification.add(this.state.error, { type: "danger" });
        }
    }

    onFilterChange(ev) {
        const field = ev.currentTarget.dataset.filter;
        const value = ev.currentTarget.value;
        this.state.filters[field] = value || null;
        this.loadDashboardData();
    }

    openModel(model, domain = []) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: domain,
        });
    }

    openCampuses() { this.openModel("oacis.campus"); }
    openStudents(state = null) {
        const dom = state ? [["student_state", "=", state]] : [];
        this.openModel("oacis.student", dom);
    }
    openApplicants() { this.openModel("oacis.admission.applicant"); }
    openFaculty() { this.openModel("oacis.faculty.member"); }
    openPrograms() { this.openModel("oacis.program"); }
    openInvoices(state = null) {
        const dom = state ? [["invoice_state", "=", state]] : [];
        this.openModel("oacis.fee.invoice", dom);
    }
    openSessions(state = null) {
        const dom = state ? [["session_state", "=", state]] : [];
        this.openModel("oacis.attendance.session", dom);
    }

    _destroyCharts() {
        Object.values(this.chartInstances).forEach((c) => c && c.destroy());
        this.chartInstances = {};
    }

    _renderCharts() {
        if (!this.state.data) return;
        this._destroyCharts();
        this._renderStudentsByState();
        this._renderStudentsByCampus();
        this._renderCampusesByType();
        this._renderInvoicesByState();
        this._renderSessionsByState();
        this._renderApplicantsByState();
    }

    _getChart() { return window.Chart; }

    _renderStudentsByState() {
        const canvas = document.querySelector("#oacisChartStudentsByState");
        if (!canvas) return;
        const data = this.state.data.charts?.students_by_state || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.studentsByState = new Chart(ctx, {
            type: "doughnut",
            data: {
                labels: data.map(d => d.label),
                datasets: [{ data: data.map(d => d.count), backgroundColor: ["#714B67", "#8B5E8C", "#A671A8", "#C291C5", "#DEB5DB", "#F0C4E8", "#FFD6E8"] }],
            },
            options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: "bottom" }, title: { display: true, text: "Students by State" } } },
        });
    }

    _renderStudentsByCampus() {
        const canvas = document.querySelector("#oacisChartStudentsByCampus");
        if (!canvas) return;
        const data = this.state.data.charts?.students_by_campus || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.studentsByCampus = new Chart(ctx, {
            type: "bar",
            data: { labels: data.map(d => d.campus_name), datasets: [{ label: "Students", data: data.map(d => d.count), backgroundColor: "#714B67" }] },
            options: { responsive: true, plugins: { legend: { display: false }, title: { display: true, text: "Students by Campus" } }, scales: { y: { beginAtZero: true } } },
        });
    }

    _renderCampusesByType() {
        const canvas = document.querySelector("#oacisChartCampusesByType");
        if (!canvas) return;
        const data = this.state.data.charts?.campuses_by_type || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.campusesByType = new Chart(ctx, {
            type: "pie",
            data: { labels: data.map(d => d.label), datasets: [{ data: data.map(d => d.count), backgroundColor: ["#714B67", "#A671A8", "#DEB5DB", "#C291C5"] }] },
            options: { responsive: true, plugins: { legend: { position: "bottom" }, title: { display: true, text: "Campuses by Type" } } },
        });
    }

    _renderInvoicesByState() {
        const canvas = document.querySelector("#oacisChartInvoicesByState");
        if (!canvas) return;
        const data = this.state.data.charts?.invoices_by_state || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.invoicesByState = new Chart(ctx, {
            type: "bar",
            data: { labels: data.map(d => d.label), datasets: [{ label: "Invoices", data: data.map(d => d.count), backgroundColor: "#7c7bad" }] },
            options: { responsive: true, plugins: { legend: { display: false }, title: { display: true, text: "Invoices by State" } }, scales: { y: { beginAtZero: true } } },
        });
    }

    _renderSessionsByState() {
        const canvas = document.querySelector("#oacisChartSessionsByState");
        if (!canvas) return;
        const data = this.state.data.charts?.sessions_by_state || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.sessionsByState = new Chart(ctx, {
            type: "doughnut",
            data: { labels: data.map(d => d.label), datasets: [{ data: data.map(d => d.count), backgroundColor: ["#00A09A", "#FFAA67", "#FF6B6B", "#7c7bad"] }] },
            options: { responsive: true, plugins: { legend: { position: "bottom" }, title: { display: true, text: "Sessions by State" } } },
        });
    }

    _renderApplicantsByState() {
        const canvas = document.querySelector("#oacisChartApplicantsByState");
        if (!canvas) return;
        const data = this.state.data.charts?.applicants_by_state || [];
        if (!data.length) return;
        const Chart = this._getChart();
        if (!Chart) return;
        const ctx = canvas.getContext("2d");
        this.chartInstances.applicantsByState = new Chart(ctx, {
            type: "bar",
            data: { labels: data.map(d => d.label), datasets: [{ label: "Applicants", data: data.map(d => d.count), backgroundColor: "#714B67", borderColor: "#714B67", borderWidth: 1 }] },
            options: { responsive: true, plugins: { legend: { display: false }, title: { display: true, text: "Applicants by State" } }, scales: { y: { beginAtZero: true } } },
        });
    }
}

registry.category("actions").add("oacis_overview_dashboard", OacisOverviewDashboard);
