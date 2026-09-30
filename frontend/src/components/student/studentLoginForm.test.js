import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'react-toastify';
import StudentLoginForm from './studentLoginForm';
import api from '../../api/students_api';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../api/students_api');

const ADMIN = { username: 'admin@studentservice.lk', password: 'admin' };
// The form stores the admin session keyed by email, not username.
const ADMIN_SESSION = { email: ADMIN.username, password: ADMIN.password };

const typeCredentials = (username, password) => {
    fireEvent.change(screen.getByPlaceholderText('Enter student Id or SLIIT email'), {
        target: { value: username },
    });
    fireEvent.change(screen.getByPlaceholderText('Enter Password'), {
        target: { value: password },
    });
};

describe('StudentLoginForm', () => {
    let authenticate;

    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
        jest.useFakeTimers();
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: { href: '' },
        });
        authenticate = jest.fn().mockResolvedValue({ data: { id: 'u1' } });
        api.studentAPI.mockReturnValue({ authenticate });
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    it('renders the login form', () => {
        render(
            <MemoryRouter>
                <StudentLoginForm />
            </MemoryRouter>
        );

        // 'Login' appears both in the card header and on the submit button.
        expect(screen.getAllByText('Login')).toHaveLength(2);
        expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /create an account/i })).toBeInTheDocument();
    });

    it('stores the admin session without calling the API', () => {
        render(
            <MemoryRouter>
                <StudentLoginForm />
            </MemoryRouter>
        );
        typeCredentials(ADMIN.username, ADMIN.password);

        fireEvent.click(screen.getByRole('button', { name: /login/i }));

        expect(authenticate).not.toHaveBeenCalled();
        expect(JSON.parse(localStorage.getItem('user'))).toEqual(ADMIN_SESSION);
        expect(toast.success).toHaveBeenCalledWith('Admin Login Success', { autoClose: 2000 });
    });

    it('authenticates a student and stores the returned user', async () => {
        render(
            <MemoryRouter>
                <StudentLoginForm />
            </MemoryRouter>
        );
        typeCredentials('IT1234', 's3cret');

        fireEvent.click(screen.getByRole('button', { name: /login/i }));

        await waitFor(() =>
            expect(authenticate).toHaveBeenCalledWith({ username: 'IT1234', password: 's3cret' })
        );
        await waitFor(() => {
            expect(JSON.parse(localStorage.getItem('user'))).toEqual({ id: 'u1' });
            expect(localStorage.getItem('userId')).toBe('u1');
            expect(toast.success).toHaveBeenCalledWith('Login Success', { autoClose: 2000 });
        });
    });

    it('surfaces the server message when authentication fails', async () => {
        authenticate.mockRejectedValue({ response: { data: 'Student Not Found.' } });
        render(
            <MemoryRouter>
                <StudentLoginForm />
            </MemoryRouter>
        );
        typeCredentials('IT1234', 'wrong');

        fireEvent.click(screen.getByRole('button', { name: /login/i }));

        await waitFor(() =>
            expect(toast.error).toHaveBeenCalledWith('Student Not Found.', { autoClose: 2000 })
        );
        expect(localStorage.getItem('user')).toBeNull();
    });

    it('sends the student to the profile after a successful login', async () => {
        render(
            <MemoryRouter>
                <StudentLoginForm />
            </MemoryRouter>
        );
        typeCredentials('IT1234', 's3cret');

        fireEvent.click(screen.getByRole('button', { name: /login/i }));
        await waitFor(() => expect(toast.success).toHaveBeenCalled());

        jest.runOnlyPendingTimers();

        expect(window.location.href).toBe('/student/profile');
    });
});
