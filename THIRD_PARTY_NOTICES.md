# Third-Party Notices

This document records the direct software dependencies and external services used by ProofPick, based on the repository manifests, lockfile, installed backend environment, source code, and deployment documentation audited on 2026-09-20. It is a compliance inventory, not legal advice, and does not replace the license texts or provider terms linked below.

ProofPick has no repository-level `LICENSE` file. Unless otherwise stated, the ProofPick source code is not distributed under an open-source license. Each third-party component remains subject to its own license, and each external service remains subject to its provider's terms.

## Direct frontend dependencies

Versions are the exact resolutions in `frontend/package-lock.json`.

| Dependency | Version | License | Category | Official source | Note |
| --- | ---: | --- | --- | --- | --- |
| Next.js (`next`) | 16.3.5 | MIT | permissive | [Next.js license](https://github.com/vercel/next.js/blob/canary/license.md) | Runtime framework. |
| React (`react`) | 19.3.0 | MIT | permissive | [React license](https://github.com/react/react/blob/main/LICENSE) | Runtime UI library. |
| React DOM (`react-dom`) | 19.3.0 | MIT | permissive | [React license](https://github.com/react/react/blob/main/LICENSE) | Runtime DOM renderer. |
| Tailwind PostCSS (`@tailwindcss/postcss`) | 4.3.3 | MIT | permissive | [Tailwind CSS license](https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE) | Development/build dependency. |
| Node.js types (`@types/node`) | 22.20.2 | MIT | permissive | [DefinitelyTyped license](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) | Development type definitions. |
| React types (`@types/react`) | 19.3.0 | MIT | permissive | [DefinitelyTyped license](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) | Development type definitions. |
| React DOM types (`@types/react-dom`) | 19.3.0 | MIT | permissive | [DefinitelyTyped license](https://github.com/DefinitelyTyped/DefinitelyTyped/blob/master/LICENSE) | Development type definitions. |
| Tailwind CSS (`tailwindcss`) | 4.3.3 | MIT | permissive | [Tailwind CSS license](https://github.com/tailwindlabs/tailwindcss/blob/main/LICENSE) | Development/build dependency. |
| TypeScript (`typescript`) | 5.9.3 | Apache-2.0 | permissive | [TypeScript license](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt) | Development compiler. |

## Direct backend dependencies

`backend/requirements.txt` specifies ranges rather than a lockfile. The versions below are the resolutions observed in the audited `backend/.venv`; a fresh installation may resolve newer compatible versions.

| Dependency | Audited version | Manifest requirement | License | Category | Official source | Note |
| --- | ---: | --- | --- | --- | --- | --- |
| FastAPI (`fastapi`) | 0.141.1 | `>=0.115,<1.0` | MIT | permissive | [FastAPI license](https://github.com/fastapi/fastapi/blob/master/LICENSE) | Runtime web framework. |
| Pydantic (`pydantic`) | 2.13.5 | `>=2.0,<3.0` | MIT | permissive | [Pydantic license](https://github.com/pydantic/pydantic/blob/main/LICENSE) | Runtime validation. |
| Uvicorn (`uvicorn[standard]`) | 0.53.0 | `>=0.30,<1.0` | BSD-3-Clause | permissive | [Uvicorn license](https://github.com/Kludex/uvicorn/blob/main/LICENSE.md) | Runtime ASGI server. |
| pytest (`pytest`) | 8.4.2 | `>=8.0,<9.0` | MIT | permissive | [pytest license](https://github.com/pytest-dev/pytest/blob/main/LICENSE) | Test dependency. |
| HTTPX (`httpx`) | 0.28.1 | `>=0.27,<1.0` | BSD-3-Clause | permissive | [HTTPX license](https://github.com/encode/httpx/blob/master/LICENSE.md) | Runtime HTTP client. |
| python-dotenv (`python-dotenv`) | 1.2.3 | `>=1.0,<2.0` | BSD-3-Clause | permissive | [python-dotenv license](https://github.com/theskumar/python-dotenv/blob/main/LICENSE) | Local environment loading. |

## Notable transitive and optional packages

The lockfile contains no transitive GPL, AGPL, SSPL, BUSL, Commons Clause, custom non-commercial, or unknown-license entries. The following non-permissive or attribution-sensitive families are called out separately. Platform-specific variants are grouped where they carry the same license metadata.

| Package family | Lockfile version | License | Category | Official source | Note |
| --- | ---: | --- | --- | --- | --- |
| `@img/sharp-libvips-*` | 1.3.3 | LGPL-3.0-or-later | weak copyleft | [sharp-libvips package metadata](https://www.npmjs.com/package/%40img/sharp-libvips-linux-x64) | Optional prebuilt libvips packages for multiple platforms. Preserve applicable license notices when redistributing binaries. |
| `@img/sharp-*` / `@img/sharp-wasm32` | 0.35.4 | Apache-2.0 AND LGPL-3.0-or-later (WASM also includes MIT) | weak copyleft | [sharp package metadata](https://www.npmjs.com/package/%40img/sharp-win32-x64) | Optional prebuilt Sharp packages; bundled third-party libraries have their own notices. |
| `lightningcss` and platform variants | 1.32.0 | MPL-2.0 | weak copyleft | [Lightning CSS repository](https://github.com/parcel-bundler/lightningcss) | Build dependency; MPL obligations apply to covered files if redistributed or modified. |
| `caniuse-lite` | 1.0.30001810 | CC-BY-4.0 | permissive (attribution) | [caniuse-lite repository](https://github.com/browserslist/caniuse-lite) | Browser support data. Attribution source: [Can I use](https://caniuse.com/). |

## External APIs and hosted services

These are proprietary services, not open-source dependencies. The links below are authoritative provider terms; account plan, usage limits, acceptable-use rules, and later updates also apply.

| Service | Terms | Category | ProofPick use | Short note |
| --- | --- | --- | --- | --- |
| OpenAI API | [OpenAI Services Agreement](https://openai.com/policies/services-agreement/) | proprietary-SaaS | Claim extraction and embeddings | API integration is permitted subject to the agreement, policies, account security, usage, content, and payment obligations. |
| Tavily Search API | [Tavily Platform Terms](https://www.tavily.com/terms) | proprietary-SaaS | Web search provider | Customer-application integration is subject to account, API-key, rate-limit, output-review, and use restrictions. |
| Vercel | [Vercel Terms of Service](https://vercel.com/legal/terms) | proprietary-SaaS | Frontend deployment | The Hobby plan is limited to personal or non-commercial use; confirm the active plan remains appropriate for the deployment. |
| Railway | [Railway Terms of Service](https://railway.com/legal/terms) | proprietary-SaaS | Backend deployment | Hosting is subject to account security, content rights, acceptable-use, and plan terms. |
| GitHub | [GitHub Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) | proprietary-SaaS | Source hosting and public repository | Repository visibility does not itself grant an open-source license; public repositories may be viewed and forked through GitHub functionality under the terms. |

## Audit summary

- No direct dependency has a GPL, AGPL, non-commercial, or unknown license in the reviewed metadata.
- The lockfile includes weak-copyleft transitive/optional packages and one CC-BY-4.0 data package; this file provides a concise notice and the requested caniuse.com attribution.
- No separate upstream `NOTICE` file was identified as mandatory for the direct dependency set reviewed here. Existing copyright and license notices must still be retained where the applicable licenses require them.
- Supabase/PostgreSQL migration files exist in the repository, but the live analysis path does not use the Supabase hosted service; Supabase is therefore not listed as an active SaaS dependency.
- Hugging Face, GLiNER, and multilingual-e5 are not present in the active dependency manifests or production code path and are not listed.
- No obvious submission conflict was identified from the reviewed service terms. Vercel plan eligibility and all provider account/usage conditions remain operational checks for the project owner.
