import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react";
import { Provider } from "react-redux";

import authReducer from "@/store/features/auth/authSlice";
import ProtectedRoute from "../page";

// inside the component we use next js's router, now javascript does not have such function, it comes with library, so we need to mock the function, so that the test runs.
jest.mock("next/navigation", () => ({
    useRouter: () => ({
        push: jest.fn(),
    }),
}));

function renderProtectedRoute(preloadedAuthState) {
    const store = configureStore({
        reducer: {
            auth: authReducer,
        },

        preloadedState: {
            auth: preloadedAuthState,
        },
    });

    return render(
        <Provider store={store}>
            <ProtectedRoute>
                <p>Protected content</p>
            </ProtectedRoute>
        </Provider>
    );
}


test('shows protected content for authenticate user with profile', () => {
    renderProtectedRoute({
        accessToken: "fake-access-token",
        refreshToken: "fake-refresh-token",
        user: {
            id: 1,
            email: "admin@example.com",
            role: "admin",
        },
        isAuthenticated: true,
        authChecked: true,
    });

    expect(screen.getByText("Protected content")).toBeInTheDocument();
});

test('does not protected content for unauthenticated user', () => {
    renderProtectedRoute({
        accessToken: null,
        refreshToken: null,
        user: null,
        isAuthenticated: false,
        authChecked: true,
    });

    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
});

