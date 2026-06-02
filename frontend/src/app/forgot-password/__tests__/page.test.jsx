import { configureStore } from "@reduxjs/toolkit";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";

import authReducer from "@/store/features/auth/authSlice";
import { api } from "@/store/api";

jest.mock("next/navigation", () => ({
    useRouter: () => ({ push: jest.fn() }),
}));

jest.mock("@/store/features/auth/authApi", () => ({
    useForgotPasswordMutation: jest.fn(),
}));

const { useForgotPasswordMutation } = require("@/store/features/auth/authApi");

function makeStore() {
    return configureStore({
        reducer: { auth: authReducer, [api.reducerPath]: api.reducer },
        middleware: (gDM) => gDM().concat(api.middleware),
    });
}

beforeEach(() => {
    useForgotPasswordMutation.mockReturnValue([jest.fn(), { isLoading: false, isSuccess: false }]);
});

import ForgotPasswordPage from "../page";

function renderPage() {
    return render(
        <Provider store={makeStore()}>
            <ForgotPasswordPage />
        </Provider>
    );
}

test("renders forgot password page", () => {
    renderPage();
    expect(screen.getByText("Forgot Password")).toBeInTheDocument();
});

test("renders email input", () => {
    renderPage();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
});

test("renders send reset link button", () => {
    renderPage();
    expect(
        screen.getByRole("button", { name: /send reset link/i })
    ).toBeInTheDocument();
});

test("shows validation error for invalid email", async () => {
    renderPage();
    const input = screen.getByLabelText("Email");
    const form = input.closest("form");

    fireEvent.change(input, { target: { value: "not-an-email" } });
    fireEvent.submit(form);

    await waitFor(() => {
        // React Hook Form + Zod should show an error message for invalid email
        const errorEl = document.querySelector("p[class*='error']");
        expect(errorEl).toBeInTheDocument();
    });
});

test("shows success screen after submission", () => {
    useForgotPasswordMutation.mockReturnValue([jest.fn(), { isLoading: false, isSuccess: true }]);
    renderPage();
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
});

test("has link back to login", () => {
    renderPage();
    const loginLink = screen.getByRole("link", { name: /login/i });
    expect(loginLink).toHaveAttribute("href", "/login");
});
