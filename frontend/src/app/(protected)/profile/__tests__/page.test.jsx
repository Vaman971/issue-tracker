import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";

import authReducer from "@/store/features/auth/authSlice";
import { api } from "@/store/api";

jest.mock("next/navigation", () => ({
    useRouter: () => ({ push: jest.fn() }),
}));

jest.mock("@/store/features/auth/authApi", () => ({
    useGetMeQuery: jest.fn(),
    useChangePasswordMutation: jest.fn(),
    useResendVerificationMutation: jest.fn(),
}));

jest.mock("@/store/features/users/usersApi", () => ({
    useUpdateProfileMutation: jest.fn(),
    useUploadAvatarMutation: jest.fn(),
}));

const { useGetMeQuery, useChangePasswordMutation, useResendVerificationMutation } =
    require("@/store/features/auth/authApi");
const { useUpdateProfileMutation, useUploadAvatarMutation } =
    require("@/store/features/users/usersApi");

const mockUser = {
    id: 1,
    email: "alice@example.com",
    full_name: "Alice Smith",
    role: "developer",
    is_active: true,
    is_email_verified: true,
    avatar_key: null,
};

function makeStore() {
    return configureStore({
        reducer: { auth: authReducer, [api.reducerPath]: api.reducer },
        middleware: (gDM) => gDM().concat(api.middleware),
        preloadedState: {
            auth: {
                accessToken: "tok",
                refreshToken: "rt",
                user: mockUser,
                isAuthenticated: true,
                authChecked: true,
            },
        },
    });
}

beforeEach(() => {
    useGetMeQuery.mockReturnValue({ data: mockUser, isLoading: false });
    useUpdateProfileMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
    useUploadAvatarMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
    useChangePasswordMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
    useResendVerificationMutation.mockReturnValue([
        jest.fn(),
        { isLoading: false, isSuccess: false },
    ]);
});

import ProfilePage from "../page";

function renderPage() {
    return render(
        <Provider store={makeStore()}>
            <ProfilePage />
        </Provider>
    );
}

test("renders profile page title", () => {
    renderPage();
    expect(screen.getByText("Your Profile")).toBeInTheDocument();
});

test("shows user email", () => {
    renderPage();
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
});

test("shows user role badge", () => {
    renderPage();
    expect(screen.getByText("developer")).toBeInTheDocument();
});

test("shows verified badge when email is verified", () => {
    renderPage();
    expect(screen.getByText("Verified")).toBeInTheDocument();
});

test("shows change password form", () => {
    renderPage();
    // "Change Password" appears as both a section heading and a button — check heading specifically
    const headings = screen.getAllByText("Change Password");
    expect(headings.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByLabelText("Current Password")).toBeInTheDocument();
    expect(screen.getByLabelText("New Password")).toBeInTheDocument();
});

test("shows avatar initial from full name", () => {
    renderPage();
    expect(screen.getByText("A")).toBeInTheDocument();
});

test("shows loading state", () => {
    useGetMeQuery.mockReturnValue({ data: undefined, isLoading: true });
    renderPage();
    expect(screen.getByText(/loading profile/i)).toBeInTheDocument();
});

test("resend verification not shown when already verified", () => {
    renderPage();
    expect(
        screen.queryByText(/resend verification/i)
    ).not.toBeInTheDocument();
});

test("resend verification shown when not verified", () => {
    useGetMeQuery.mockReturnValue({
        data: { ...mockUser, is_email_verified: false },
        isLoading: false,
    });
    renderPage();
    expect(
        screen.getByText(/resend verification email/i)
    ).toBeInTheDocument();
});
