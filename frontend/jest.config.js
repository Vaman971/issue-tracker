const nextJest = require("next/jest");

const createJestConfig = nextJest({ dir: "./" });

const customJestConfig = {
    testEnvironment: "jest-environment-jsdom",
    setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],

    moduleNameMapper: {
        "^@/(.*)$": "<rootDir>/src/$1",
    },

    // Explicitly use babel-jest with next/babel so JSX is always supported in CI,
    // regardless of which platform-specific SWC binary is available.
    // next/babel includes @babel/preset-react, @babel/preset-env, and TypeScript support.
    transform: {
        "^.+\\.(js|jsx|mjs|cjs|ts|tsx)$": [
            "babel-jest",
            { presets: ["next/babel"] },
        ],
    },
};

module.exports = createJestConfig(customJestConfig);
