import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Home from './home';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

describe('Home', () => {
    it('renders the landing content and a link to registration', () => {
        render(
            <MemoryRouter>
                <Home />
            </MemoryRouter>
        );

        expect(screen.getByText('SLIIT')).toBeInTheDocument();
        expect(screen.getByText(/Cloud Computing Assignment 1/)).toBeInTheDocument();
        expect(screen.getByRole('link', { name: /start/i }))
            .toHaveAttribute('href', '/student/new');
    });

    it('shows the project logo', () => {
        render(
            <MemoryRouter>
                <Home />
            </MemoryRouter>
        );

        expect(screen.getByAltText('sliit-logo')).toBeInTheDocument();
    });
});
