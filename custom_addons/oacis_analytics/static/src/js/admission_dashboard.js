/** @odoo-module **/

import { Component, onMounted, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AdmissionDashboard extends Component {
    static template = "oacis_analytics.AdmissionDashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.hasChartJs = typeof window.Chart !== 'undefined';

        this.state = useState({
            data: null,
            loading: true,
            filters: {
                academic_year_id: null,
                campus_id: null,
                program_id: null,
                state: null,
                date_from: null,
                date_to: null,
            },
            error: null,
        });

        this.chartInstances = {};

        onMounted(() => {
            this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            // Build domain from filters
            const domain = this._buildDomain();

            // Call the aggregation method
            const data = await this.orm.call(
                "oacis.admission.applicant",
                "get_admission_dashboard_data",
                [domain]
            );

            this.state.data = data;
            this.state.loading = false;

            // Defer chart rendering until after DOM is ready
            setTimeout(() => this._renderCharts(), 100);
        } catch (error) {
            this.state.error = error.message || "Failed to load dashboard data";
            this.state.loading = false;
            this.notification.add(this.state.error, { type: "danger" });
        }
    }

    _buildDomain() {
        const domain = [];

        if (this.state.filters.academic_year_id) {
            domain.push(['cycle_id.academic_year_id', '=', this.state.filters.academic_year_id]);
        }
        if (this.state.filters.campus_id) {
            domain.push(['campus_id', '=', this.state.filters.campus_id]);
        }
        if (this.state.filters.program_id) {
            domain.push(['program_id', '=', this.state.filters.program_id]);
        }
        if (this.state.filters.state) {
            domain.push(['state', '=', this.state.filters.state]);
        }
        if (this.state.filters.date_from) {
            domain.push(['create_date', '>=', this.state.filters.date_from]);
        }
        if (this.state.filters.date_to) {
            // Add 1 day to include the entire day
            const toDate = new Date(this.state.filters.date_to);
            toDate.setDate(toDate.getDate() + 1);
            domain.push(['create_date', '<', toDate.toISOString().split('T')[0]]);
        }

        return domain;
    }

    onFilterChange(ev) {
        const field = ev.currentTarget.dataset.field;
        const value = ev.currentTarget.value;
        this.state.filters[field] = value || null;
        this.loadDashboardData();
    }

    _renderCharts() {
        if (!this.state.data) return;

        // Destroy existing charts
        Object.values(this.chartInstances).forEach(chart => {
            if (chart) chart.destroy();
        });
        this.chartInstances = {};

        // Render funnel chart
        this._renderFunnelChart();

        // Render applications over time chart
        this._renderApplicationsOverTimeChart();

        // Render by-program chart
        this._renderByProgramChart();

        // Render by-campus chart
        this._renderByCampusChart();

        // Render by-gender chart
        this._renderByGenderChart();
    }

    _renderFunnelChart() {
        const canvas = this.el?.querySelector('#funnelChart');
        if (!canvas) return;

        const funnel = this.state.data.funnel || [];
        const maxCount = Math.max(...funnel.map(f => f.count || 0));

        const ctx = canvas.getContext('2d');
        const Chart = window.Chart;

        if (Chart) {
            this.chartInstances.funnel = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: funnel.map(f => f.label),
                    datasets: [{
                        label: 'Applicants',
                        data: funnel.map(f => f.count),
                        backgroundColor: '#714B67',
                        borderColor: '#714B67',
                        borderWidth: 1,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    indexAxis: 'y',
                    scales: {
                        x: {
                            beginAtZero: true,
                            max: maxCount * 1.1,
                        },
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Application Funnel' },
                    },
                },
            });
        }
    }

    _renderApplicationsOverTimeChart() {
        const canvas = this.el?.querySelector('#applicationsOverTimeChart');
        if (!canvas) return;

        const data = this.state.data.applications_over_time || [];
        if (data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const Chart = window.Chart;

        if (Chart) {
            this.chartInstances.overTime = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.map(d => d.month),
                    datasets: [{
                        label: 'Applications',
                        data: data.map(d => d.count),
                        borderColor: '#714B67',
                        backgroundColor: 'rgba(113, 75, 103, 0.1)',
                        tension: 0.4,
                        fill: true,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        y: { beginAtZero: true },
                    },
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Applications Over Time' },
                    },
                },
            });
        }
    }

    _renderByProgramChart() {
        const canvas = this.el?.querySelector('#byProgramChart');
        if (!canvas) return;

        const data = this.state.data.by_program || [];
        if (data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const Chart = window.Chart;

        if (Chart) {
            this.chartInstances.byProgram = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.program_name),
                    datasets: [{
                        label: 'Applicants',
                        data: data.map(d => d.count),
                        backgroundColor: '#714B67',
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { display: false },
                        title: { display: true, text: 'Applications by Program' },
                    },
                    scales: { y: { beginAtZero: true } },
                },
            });
        }
    }

    _renderByCampusChart() {
        const canvas = this.el?.querySelector('#byCampusChart');
        if (!canvas) return;

        const data = this.state.data.by_campus || [];
        if (data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const Chart = window.Chart;

        if (Chart) {
            this.chartInstances.byCampus = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.map(d => d.campus_name),
                    datasets: [{
                        data: data.map(d => d.count),
                        backgroundColor: [
                            '#714B67', '#8B5E8C', '#A671A8', '#C291C5', '#DEB5DB',
                        ],
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { position: 'bottom' },
                        title: { display: true, text: 'Distribution by Campus' },
                    },
                },
            });
        }
    }

    _renderByGenderChart() {
        const canvas = this.el?.querySelector('#byGenderChart');
        if (!canvas) return;

        const data = this.state.data.by_gender || [];
        if (data.length === 0) return;

        const ctx = canvas.getContext('2d');
        const Chart = window.Chart;

        if (Chart) {
            this.chartInstances.byGender = new Chart(ctx, {
                type: 'pie',
                data: {
                    labels: data.map(d => d.label),
                    datasets: [{
                        data: data.map(d => d.count),
                        backgroundColor: ['#714B67', '#A671A8', '#DEB5DB'],
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                        legend: { position: 'bottom' },
                        title: { display: true, text: 'Distribution by Gender' },
                    },
                },
            });
        }
    }
}

// Register as a standard client action
registry.category("actions").add("oacis_admission_dashboard", AdmissionDashboard);
