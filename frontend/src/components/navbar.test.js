import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { toast } from 'react-toastify';
import NavBar from './navbar';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

const renderNav = () =>
    render(
        <MemoryRouter>
            <NavBar />
        </MemoryRouter>
    );

describe('Navbar', () => {
    beforeEach(() => {
        localStorage.clear();
        jest.clearAllMocks();
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: { href: '' },
        });
    });

    it('offers register and login to a guest', () => {
        renderNav();

        expect(screen.getByRole('link', { name: /register student/i })).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /login/i })).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /logout/i })).not.toBeInTheDocument();
    });

    it('offers the profile to a signed-in student', () => {
        localStorage.setItem('user', JSON.stringify({ email: 'jane@example.com' }));

        renderNav();

        expect(screen.getByRole('link', { name: /profile/i })).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /register student/i })).not.toBeInTheDocument();
    });

    it('offers the staff dashboard to the admin', () => {
        localStorage.setItem(
            'user',
            JSON.stringify({ email: 'admin@studentservice.lk', password: 'admin' })
        );

        renderNav();

        expect(screen.getByRole('link', { name: /student dashboard/i })).toBeInTheDocument();
        expect(screen.queryByRole('link', { name: /profile/i })).not.toBeInTheDocument();
    });

    it('clears the session and confirms on logout', () => {
        localStorage.setItem('user', JSON.stringify({ email: 'jane@example.com' }));
        localStorage.setItem('userId', 'abc');

        renderNav();
        fireEvent.click(screen.getByRole('link', { name: /logout/i }));

        expect(toast.success).toHaveBeenCalledWith('logout Success.', { autoClose: 2000 });
        expect(localStorage.getItem('user')).toBeNull();
        expect(localStorage.getItem('userId')).toBeNull();
        expect(window.location.href).toBe('/student/login');
    });
});
