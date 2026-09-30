import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';
import StudentProfile from './StudentProfile';
import api from '../../api/students_api';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../api/students_api');

const USER = {
    firstName: 'Jane',
    lastName: 'Doe',
    studentId: 'IT1234',
    email: 'jane@example.com',
    password: 's3cret',
};

const renderProfile = () => render(<StudentProfile />);

// onSubmit builds its payload from `e.target.firstName.value`, relying on the
// browser exposing form fields as named properties of the <form>. jsdom does
// not implement that getter, so the fields are attached explicitly here rather
// than changing correct application code.
const submitProfile = (container) => {
    const form = container.querySelector('form');
    form.querySelectorAll('input').forEach((input) => {
        if (input.name) {
            form[input.name] = input;
        }
    });
    fireEvent.submit(form);
};

describe('StudentProfile', () => {
    let getStudentDataById;
    let updateStudentDataById;
    let deleteStudentDataById;

    beforeEach(() => {
        jest.clearAllMocks();
        localStorage.clear();
        localStorage.setItem('user', JSON.stringify(USER));
        jest.useFakeTimers();
        Object.defineProperty(window, 'location', {
            configurable: true,
            value: { href: '' },
        });
        global.URL.createObjectURL = jest.fn(() => 'blob:preview');
        getStudentDataById = jest.fn().mockResolvedValue({ data: USER });
        updateStudentDataById = jest.fn().mockResolvedValue({ data: {} });
        deleteStudentDataById = jest.fn().mockResolvedValue({ data: {} });
        api.studentAPI.mockReturnValue({
            getStudentDataById,
            updateStudentDataById,
            deleteStudentDataById,
        });
    });

    afterEach(() => {
        jest.useRealTimers();
    });

    it('fetches the signed-in student and shows the details', async () => {
        renderProfile();

        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());
        expect(getStudentDataById).toHaveBeenCalledWith('IT1234');
        expect(screen.getByDisplayValue('jane@example.com')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Jane')).toBeInTheDocument();
    });

    it('reports a failed load', async () => {
        getStudentDataById.mockRejectedValue({ response: { status: 500 } });

        renderProfile();

        await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });

    it('edits each field of the loaded student', async () => {
        renderProfile();
        await waitFor(() => expect(screen.getByDisplayValue('Jane')).toBeInTheDocument());

        fireEvent.change(screen.getByDisplayValue('Jane'), { target: { value: 'Janet' } });
        fireEvent.change(screen.getByDisplayValue('Doe'), { target: { value: 'Roe' } });
        fireEvent.change(screen.getByDisplayValue('jane@example.com'), {
            target: { value: 'janet@example.com' },
        });

        expect(screen.getByDisplayValue('Janet')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Roe')).toBeInTheDocument();
        expect(screen.getByDisplayValue('janet@example.com')).toBeInTheDocument();
    });

    it('previews a selected profile picture', async () => {
        const { container } = renderProfile();
        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());

        const file = new File(['x'], 'avatar.png', { type: 'image/png' });
        fireEvent.change(document.querySelector('input[type="file"]'), {
            target: { files: [file] },
        });

        expect(global.URL.createObjectURL).toHaveBeenCalledWith(file);
        expect(container.querySelector('img').getAttribute('src')).toBe('blob:preview');
    });

    it('updates the student once the change is confirmed', async () => {
        window.confirm = jest.fn(() => true);
        const { container } = renderProfile();
        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());

        fireEvent.change(screen.getByDisplayValue('Jane'), { target: { value: 'Janet' } });
        submitProfile(container);

        await waitFor(() =>
            expect(updateStudentDataById).toHaveBeenCalledWith('IT1234', {
                firstName: 'Janet',
                lastName: 'Doe',
                studentId: 'IT1234',
                email: 'jane@example.com',
                password: 's3cret',
            })
        );
        expect(toast.success).toHaveBeenCalledWith('Your Data is Updated.', { autoClose: 2000 });
    });

    it('does nothing when the update is cancelled', async () => {
        window.confirm = jest.fn(() => false);
        const { container } = renderProfile();
        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());

        submitProfile(container);

        expect(updateStudentDataById).not.toHaveBeenCalled();
    });

    it('deletes the account and clears the session once confirmed', async () => {
        window.confirm = jest.fn(() => true);
        renderProfile();
        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());

        fireEvent.click(screen.getByRole('button', { name: /delete my account/i }));

        await waitFor(() => expect(deleteStudentDataById).toHaveBeenCalledWith('IT1234'));
        await waitFor(() => expect(localStorage.getItem('user')).toBeNull());
        expect(toast.success).toHaveBeenCalledWith('Your Account Successfully Deleted.', {
            autoClose: 2000,
        });
    });

    it('keeps the account when the deletion is cancelled', async () => {
        window.confirm = jest.fn(() => false);
        renderProfile();
        await waitFor(() => expect(screen.getByText(/My Profile/)).toBeInTheDocument());

        fireEvent.click(screen.getByRole('button', { name: /delete my account/i }));

        expect(deleteStudentDataById).not.toHaveBeenCalled();
        expect(localStorage.getItem('user')).not.toBeNull();
    });
});
