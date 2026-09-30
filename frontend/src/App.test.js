import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

const ADMIN = { email: 'admin@studentservice.lk', password: 'admin' };
const STUDENT = { email: 'jane@example.com', password: 's3cret' };

const navLinks = () =>
    screen.getAllByRole('link').map((link) => link.textContent.trim());

describe('App', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    it('routes a guest to register and login', () => {
        render(<App />);

        expect(navLinks()).toEqual(
            expect.arrayContaining(['Student Service', 'Register Student', 'Login'])
        );
    });

    it('routes a signed-in student to their profile', () => {
        localStorage.setItem('user', JSON.stringify(STUDENT));

        render(<App />);

        expect(navLinks()).toEqual(expect.arrayContaining(['Student Service', 'Profile']));
        expect(navLinks()).not.toContain('Register Student');
    });

    it('routes the admin to the student dashboard', () => {
        localStorage.setItem('user', JSON.stringify(ADMIN));

        render(<App />);

        expect(navLinks()).toEqual(
            expect.arrayContaining(['Student Service', 'Student Dashboard'])
        );
        expect(navLinks()).not.toContain('Profile');
    });

    it('renders the landing page at the root route', () => {
        render(<App />);

        expect(screen.getByText('SLIIT')).toBeInTheDocument();
        expect(screen.getByText(/Cloud Computing Assignment 1/)).toBeInTheDocument();
    });
});
