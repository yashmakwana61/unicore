import React from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';

const workflows = [
  ['Institution Setup & Roles','Configure company details, profiles, administrators and permissions.','settings_institution'],
  ['Academic Calendar','Create academic years and semesters with required confirmations.','teaching_calendar'],
  ['Academic Structure','Set up campuses, departments, faculties, programs and buildings.','teaching_structure'],
  ['Student Life','Create and enroll students, manage guardians and discipline records.','student_life'],
  ['Admissions','Configure admission cycles, allocate seats and create applicants.','admissions'],
  ['Finance','Set up fees, issue invoices, post to GL and reconcile payments.','finance'],
  ['Examinations','Prepare offerings, hall tickets, seating, grades and results.','examinations'],
  ['Campus Operations','Manage facilities, rooms, transport and documented access limits.','campus_ops'],
  ['Careers','Work with placements, scholarships and alumni relationships.','careers'],
  ['Insights & Reports','Use and validate student, attendance, grade and fee analytics.','insights'],
  ['Communications & AI','Manage notices, notifications and AI availability safely.','comms_ai'],
  ['Website & Apps','Review public website and module administration safely.','website_apps']
];
export default function Home(){return <Layout title="Administrator Workflow Guides" description="Screenshot-backed Edicai ERP administrator workflows"><main><section className="cf-hero"><div className="cf-hero-inner"><p className="cf-eyebrow">Edicai administrator training</p><h1 className="cf-title">Real workflows.<br/>Practical guidance.</h1><p className="cf-desc">Follow documented workflows from the Edicai UAT walkthrough, with step-by-step guidance, screenshots and known limitations. Unverified module reference and placeholder pages are hidden until their workflows are documented.</p><div className="cf-actions"><Link to="/docs/training/overview" className="cf-btn cf-btn-primary">Start administrator training →</Link><Link to="/docs/training/quick_reference" className="cf-btn cf-btn-muted">Quick reference</Link></div></div></section><section className="cf-section"><p className="cf-eyebrow">Verified UAT walkthroughs</p><h2>Explore administrator workflows</h2><p>Each guide describes the recorded UAT steps and flags any incomplete or blocked actions. Confirm configuration and permissions in your institution before applying it in production.</p><div className="cf-grid">{workflows.map(([title,description,slug])=><Link key={slug} to={'/docs/training/'+slug} className="cf-card"><h3>{title} →</h3><p>{description}</p></Link>)}</div></section><section className="cf-section"><p className="cf-eyebrow">Administrator reference</p><h2>Find the correct setup order</h2><p>Review dependencies and implementation checklists before starting a workflow.</p><Link className="cf-btn cf-btn-primary" to="/docs/training/quick_reference">Open quick reference →</Link></section></main></Layout>}
