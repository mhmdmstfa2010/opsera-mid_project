import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';
import StudentDashboard from './studentDashboard';
import api from '../../api/students_api';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../api/students_api');

const STUDENTS = [
    { firstName: 'Jane', lastName: 'Doe', studentId: 'IT1234', email: 'jane@example.com' },
    { firstName: 'John', lastName: 'Roe', studentId: 'IT5678', email: 'john@example.com' },
];

const renderDashboard = () => render(<StudentDashboard />);

describe('StudentDashboard', () => {
    let getAllStudents;
    let deleteStudentDataById;

    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
        localStorage.setItem('user', JSON.stringify({ email: 'admin@studentservice.lk' }));
        getAllStudents = jest.fn().mockResolvedValue({ data: STUDENTS });
        deleteStudentDataById = jest.fn().mockResolvedValue({ data: {} });
        api.studentAPI.mockReturnValue({ getAllStudents, deleteStudentDataById });
    });

    it('lists every student returned by the API', async () => {
        renderDashboard();

        await waitFor(() => expect(screen.getByText('jane@example.com')).toBeInTheDocument());
        expect(getAllStudents).toHaveBeenCalled();
        expect(screen.getByText('john@example.com')).toBeInTheDocument();
        expect(screen.getAllByRole('button', { name: /delete/i })).toHaveLength(2);
    });

    it('reports a failed load', async () => {
        getAllStudents.mockRejectedValue({ response: { status: 500 } });

        renderDashboard();

        await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });

    it('filters the table by email as the search box changes', async () => {
        renderDashboard();
        await waitFor(() => expect(screen.getByText('jane@example.com')).toBeInTheDocument());

        fireEvent.change(screen.getByPlaceholderText('Find student from email'), {
            target: { value: 'john' },
        });

        expect(screen.queryByText('jane@example.com')).not.toBeInTheDocument();
        expect(screen.getByText('john@example.com')).toBeInTheDocument();
    });

    it('caps the search term at twenty characters', async () => {
        renderDashboard();
        await waitFor(() => expect(screen.getByText('jane@example.com')).toBeInTheDocument());

        fireEvent.change(screen.getByPlaceholderText('Find student from email'), {
            target: { value: 'x'.repeat(30) },
        });

        expect(screen.getByPlaceholderText('Find student from email')).toHaveValue('x'.repeat(20));
    });

    it('deletes the student after confirmation and reloads the list', async () => {
        window.confirm = jest.fn(() => true);
        renderDashboard();
        await waitFor(() => expect(screen.getByText('jane@example.com')).toBeInTheDocument());

        fireEvent.click(screen.getAllByRole('button', { name: /delete/i })[0]);

        await waitFor(() => expect(deleteStudentDataById).toHaveBeenCalledWith('IT1234'));
        await waitFor(() =>
            expect(toast.success).toHaveBeenCalledWith('Student Successfully Deleted', {
                autoClose: 2000,
            })
        );
        expect(getAllStudents).toHaveBeenCalledTimes(2);
    });

    it('does not delete when the confirmation is declined', async () => {
        window.confirm = jest.fn(() => false);
        renderDashboard();
        await waitFor(() => expect(screen.getByText('jane@example.com')).toBeInTheDocument());

        fireEvent.click(screen.getAllByRole('button', { name: /delete/i })[0]);

        expect(deleteStudentDataById).not.toHaveBeenCalled();
    });
});
