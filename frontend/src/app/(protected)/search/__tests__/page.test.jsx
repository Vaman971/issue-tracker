import { configureStore } from "@reduxjs/toolkit";
import { render, screen, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";

import authReducer from "@/store/features/auth/authSlice";
import { api } from "@/store/api";

jest.mock("next/navigation", () => ({
    useRouter: () => ({ push: jest.fn() }),
    useSearchParams: () => ({ get: jest.fn().mockReturnValue("") }),
}));

jest.mock("@/store/features/search/searchApi", () => ({
    useSearchQuery: jest.fn(),
}));

const { useSearchQuery } = require("@/store/features/search/searchApi");

function makeStore() {
    return configureStore({
        reducer: { auth: authReducer, [api.reducerPath]: api.reducer },
        middleware: (gDM) => gDM().concat(api.middleware),
        preloadedState: {
            auth: {
                accessToken: "tok",
                refreshToken: "rt",
                user: { id: 1, email: "user@test.com", role: "viewer" },
                isAuthenticated: true,
                authChecked: true,
            },
        },
    });
}

beforeEach(() => {
    useSearchQuery.mockReturnValue({
        data: null,
        isLoading: false,
        isFetching: false,
    });
});

import SearchPage from "../page";

function renderPage() {
    return render(
        <Provider store={makeStore()}>
            <SearchPage />
        </Provider>
    );
}

test("renders search page", () => {
    renderPage();
    expect(screen.getByText("Find anything")).toBeInTheDocument();
});

test("has search input", () => {
    renderPage();
    expect(
        screen.getByPlaceholderText(/search issues and projects/i)
    ).toBeInTheDocument();
});

test("search button is disabled with short query", () => {
    renderPage();
    const button = screen.getByRole("button", { name: /search/i });
    expect(button).toBeDisabled();
});

test("shows loading state", () => {
    useSearchQuery.mockReturnValue({ data: null, isLoading: true, isFetching: true });
    renderPage();
    const input = screen.getByPlaceholderText(/search issues and projects/i);
    fireEvent.change(input, { target: { value: "test" } });
    // "Searching..." appears in both the button and the <p> loading text
    const searchingEls = screen.getAllByText(/searching\.\.\./i);
    expect(searchingEls.length).toBeGreaterThanOrEqual(1);
});

test("shows search results with issues", () => {
    useSearchQuery.mockReturnValue({
        data: {
            issues: [
                {
                    id: 1,
                    title: "Login bug",
                    description: "User cannot log in",
                    priority: "high",
                    status: "todo",
                },
            ],
            projects: [],
        },
        isLoading: false,
        isFetching: false,
    });

    renderPage();

    // Submit a query to show results
    const input = screen.getByPlaceholderText(/search issues and projects/i);
    fireEvent.change(input, { target: { value: "Login" } });
    fireEvent.submit(input.closest("form"));

    expect(screen.getByText("Login bug")).toBeInTheDocument();
});

test("shows search results with projects", () => {
    useSearchQuery.mockReturnValue({
        data: {
            issues: [],
            projects: [{ id: 10, name: "My Project", description: "A project" }],
        },
        isLoading: false,
        isFetching: false,
    });

    renderPage();

    const input = screen.getByPlaceholderText(/search issues and projects/i);
    fireEvent.change(input, { target: { value: "My" } });
    fireEvent.submit(input.closest("form"));

    expect(screen.getByText("My Project")).toBeInTheDocument();
});
