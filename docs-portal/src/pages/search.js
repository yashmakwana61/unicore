import React,{useState} from 'react';
import Layout from '@theme/Layout';
import Link from '@docusaurus/Link';
const guides = [
 ['Administrator Training Overview','Guide contents, prerequisites and UAT limitations','overview','start setup introduction'],
 ['Getting Started & Orientation','Log in, navigate Home and understand optional onboarding','getting_started','login dashboard'],
 ['Institution Settings & Users','Institution profiles, company settings, administrator roles and access','settings_institution','company user role permissions'],
 ['Academic Years & Semesters','Academic calendar, years, terms and confirmation guards','teaching_calendar','year semester calendar'],
 ['Academic Structure & Campuses','Buildings, faculties, departments, programs and their dependencies','teaching_structure','academic faculty campus program'],
 ['Student Life','Students, enrollment, guardians and discipline','student_life','guardian student'],
 ['Admissions','Admission cycle, seat allocation and application stages','admissions','applicants pipeline'],
 ['Finance','Fee structures, invoices, GL and payment reconciliation','finance','billing accounting'],
 ['Examinations','Attendance eligibility, hall tickets, seating, grading and results','examinations','exams'],
 ['Campus Operations','Facilities, rooms, routes, transport passes and appointments','campus_ops','transport'],
 ['Careers','Placement drives, applications, scholarships and alumni','careers','recruitment'],
 ['Insights & Reports','Enrollment, attendance, grades and collection analytics','insights','dashboard analytics'],
 ['Communications & AI','Notices, notifications and AI provider availability','comms_ai','messages'],
 ['Website & Apps','Website release checks and Apps administration','website_apps','modules content'],
 ['Administrator Quick Reference','Setup sequence, checks, and operational safety rules','quick_reference','cheat sheet']
];
export default function Search(){const [query,setQuery]=useState('');const q=query.trim().toLowerCase();const hits=q?guides.filter(x=>[x[0],x[1],x[3]].join(' ').toLowerCase().includes(q)):guides;return <Layout title="Search Workflows"><main className="cf-section"><p className="cf-eyebrow">Workflow search</p><h1>Find an administrator workflow</h1><p>Search the published workflow guides. Draft and reference-only modules are not shown.</p><input className="cf-search" aria-label="Search Edicai workflows" placeholder="Search admissions, fees, grading, campus…" autoFocus value={query} onChange={e=>setQuery(e.target.value)}/><p>{hits.length} guides shown</p><div className="cf-results">{hits.map(x=><Link className="cf-result" to={'/docs/training/'+x[2]} key={x[2]}><strong>{x[0]} →</strong><small>{x[1]}</small></Link>)}</div></main></Layout>}
