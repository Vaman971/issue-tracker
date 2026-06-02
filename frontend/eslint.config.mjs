import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";

const eslintConfig = defineConfig([
    ...nextVitals,
    globalIgnores([
        ".next/**",
        "out/**",
        "build/**",
        "next-env.d.ts",
    ]),
    {
        rules: {
            // setState inside useEffect is a legitimate pattern for:
            // - page-reset on search change (with debounce)
            // - SSR hydration guard (setMounted)
            // - form reset on modal open
            // - one-time side effects guarded by a flag
            "react-hooks/set-state-in-effect": "off",
        },
    },
]);

export default eslintConfig;
