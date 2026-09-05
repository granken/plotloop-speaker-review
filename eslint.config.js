import js from "@eslint/js";

export default [
    js.configs.recommended,
    {
        files: ["src/**/*.js"],
        languageOptions: {
            globals: {
                window: "readonly",
                document: "readonly",
                FileReader: "readonly",
                Blob: "readonly",
                URL: "readonly",
                localStorage: "readonly",
                navigator: "readonly",
                fetch: "readonly",
                URLSearchParams: "readonly",
                module: "readonly"
            },
        },
        rules: {
            "no-var": "error",
            "prefer-const": "error"
        }
    }
];
