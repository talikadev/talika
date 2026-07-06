---
icon: lucide/table-properties
title: Talika
---

<style> .md-content .md-typeset h1 { display: none; } </style>
<style>
.md-content .md-typeset a {
  color: inherit;
  text-decoration: none;
}
</style>

<style>
.md-typeset code {
  background: linear-gradient(90deg, #cb0663, #f8a130);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  box-shadow: none;
}
</style>

<p align="center">
  <a><img src="http://localhost:8000/assets/images/logotalpha_400.png" alt="Talika"></a>
</p>

<p align="center">
  Talika - <strong><em>Hindi for Tables</em></strong>
  <svg xmlns="http://www.w3.org/2000/svg"
       width="22"
       height="22"
       viewBox="0 -2 24 24"
       fill="none"
       stroke="url(#table-icon-gradient)"
       stroke-width="2"
       stroke-linecap="round"
       stroke-linejoin="round">

    <defs>
      <linearGradient id="table-icon-gradient" x1="3" y1="3" x2="21" y2="21" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#ef1266" />
        <stop offset="100%" stop-color="#fea22f" />
      </linearGradient>
    </defs>

    <rect width="18" height="18" x="3" y="3" rx="2"/>
    <path d="M3 9h18"/>
    <path d="M3 15h18"/>
    <path d="M9 3v18"/>
    <path d="M15 3v18"/>
  </svg>
</br>
Declarative schemas for your test data tables.
</p>

<p align="center">

<a href="https://github.com/chinmaysingh31/bdd-tablex/actions?query=event%3Apush+branch%3Amaster">
    <img src="https://github.com/chinmaysingh31/bdd-tablex/actions/workflows/ci.yml/badge.svg?event=push&branch=master" alt="Test">
</a>

<a href="https://pypi.org/project/fastapi">
    <img src="https://img.shields.io/pypi/v/fastapi?color=%2334D058&label=pypi%20package" alt="Package version">
</a>

<a href="https://pypi.org/project/fastapi">
    <img src="https://img.shields.io/pypi/pyversions/fastapi.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

----
<p align="center">
<em>Define your table shape once with Python types and descriptors.</em>
</br>

Talika handles parsing, cell conversion, validation, and precise error reporting — and lets your team define its own readable cell conventions instead of fighting <code>list[list[str]]</code>

</p>

The key features are:

- **Short**: Eliminate manual parsing boilerplate and stop slicing raw `list[list[str]]` inputs.
- **Typed**: Declare your schema using standard Python types for automatic cell conversion.
- **Fewer bugs**: Validate required fields and exact types before your test steps even execute.
- **Pinpoint errors**: Get exact line and column locations in your `.feature` file when data fails validation.
- **Expressive**: Define custom `cell conventions`, fallbacks, and regex matchers with the `built-in DSL`.
- **Polymorphic**: Parse rows representing completely different object types using `clean variant schemas`.
- **Flexible**: Support both Row-oriented (lists) and Column-oriented (single items) tables seamlessly.
- **Static validation**: Use the `talika check` CLI to validate Gherkin tables in CI without booting your test suite.


```bash { .talika-terminal .speed-1 title="Built By" }
$ Chinmay
Github - https://github.com/chinmaysingh31
Email - chinmay@gmail.com
$ Nishant
Github - https://github.com/github
Email - nishant@gmail.com
```