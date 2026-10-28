# FDR Guardian visual theme

This frontend restyle uses the existing React, Tailwind, shadcn, and Lucide setup. The visual reference supplied for this work informed the palette, portal layout, emblem placement, and footer structure. Its application code, sample data, and behaviour were not copied. The only copied asset is `frontend/public/indian-state-emblem.png`.

## Design tokens

Tokens live in `frontend/src/styles.css` on `:root` and are shared by page styles and the shadcn variables:

| Variable | Value | Use |
| --- | --- | --- |
| `--navy` | `#17306b` | Headings and deep brand accents |
| `--navy2` | `#1f4aa8` | Primary actions, active navigation and links |
| `--saf` | `#ff9933` | Saffron accent |
| `--grn` | `#138808` | Green status and accent |
| `--red` | `#c62828` | Alert and destructive emphasis |
| `--amb` | `#b45f06` | Warning emphasis |
| `--bg` | `#f5f6f9` | Page background |
| `--card` | `#fff` | Surfaces |
| `--ink` | `#1f2430` | Main text |
| `--mute` | `#5d6678` | Secondary text |
| `--line` | `#e3e8f1` | Borders and dividers |
| `--tint` | `#eef3fd` | Soft blue surface |

The base font is 16px with `Noto Sans`, `Segoe UI`, and Arial fallbacks. A sticky header contains permission-filtered horizontal navigation, registry search, account actions, and in-memory text-size and high-contrast controls. The dashboard hero and KPI values use existing API data. All existing routes, permission checks, and API operations remain the source of application behavior.

## Government identity display

Brand identity text and the configuration flag are centralized in `frontend/src/config/branding.ts`. Government identity display defaults on. To turn it off for public hosting, set this Vite environment variable in the hosting environment and rebuild/redeploy:

```text
VITE_SHOW_GOV_BRANDING=false
```

With the flag off, header, login and footer identities use a neutral shield and FDR Guardian/demo wording in place of the emblem and government identity labels. The non-dismissible prototype notice and footer disclaimer remain visible in both modes. The public-build setting can be checked in Vercel under Project Settings → Environment Variables; add it for the desired deployment environments and redeploy.

## Accessibility

The skip link targets the main content, controls retain accessible names and pressed states, and visible keyboard focus uses a 3px saffron-tinted outline. Text-size and high-contrast preferences are React memory state only and reset on page reload. The high-contrast mode switches the `html` element to `.hc` variables.
