import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { toast } from 'react-toastify';
import StudentRegisterForm from './StudentRegisterForm';
import api from '../../api/students_api';

jest.mock('react-toastify', () => ({
    toast: { configure: jest.fn(), success: jest.fn(), error: jest.fn() },
}));

jest.mock('../../api/students_api');

// The component reads its payload as `e.target.firstName.value`, relying on
// the browser exposing form fields as named properties of the <form>. jsdom
// does not implement that getter, so the fields are attached explicitly here.
// The application code is correct and is deliberately left untouched.
const submit = (container) => {
    const form = container.querySelector('form');
    form.querySelectorAll('input').forEach((input) => {
        if (input.name) {
            form[input.name] = input;
        }
    });
    fireEvent.submit(form);
};

const fillForm = () => {
    fireEvent.change(screen.getByPlaceholderText('First name'), {
        target: { value: 'Jane' },
    });
    fireEvent.change(screen.getByPlaceholderText('Last name'), {
        target: { value: 'Doe' },
    });
    fireEvent.change(screen.getByPlaceholderText('Enter Student ID'), {
        target: { value: 'IT1234' },
    });
    fireEvent.change(screen.getByPlaceholderText('Enter email'), {
        target: { value: 'jane@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Enter Password'), {
        target: { value: 's3cret' },
    });
};

describe('StudentRegisterForm', () => {
    let newStudent;

    beforeEach(() => {
        jest.clearAllMocks();
        newStudent = jest.fn().mockResolvedValue({ data: {} });
        api.studentAPI.mockReturnValue({ newStudent });
    });

    it('renders every field of the registration form', () => {
        render(<StudentRegisterForm />);

        expect(screen.getByText('New Student')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('First name')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Last name')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Enter Student ID')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Enter email')).toBeInTheDocument();
        expect(screen.getByPlaceholderText('Enter Password')).toBeInTheDocument();
    });

    it('submits the entered values as one student object', async () => {
        const { container } = render(<StudentRegisterForm />);
        fillForm();

        submit(container);

        await waitFor(() => expect(newStudent).toHaveBeenCalledWith({
            firstName: 'Jane',
            lastName: 'Doe',
            studentId: 'IT1234',
            email: 'jane@example.com',
            password: 's3cret',
        }));
    });

    it('confirms success when the student is created', async () => {
        const { container } = render(<StudentRegisterForm />);
        fillForm();

        submit(container);

        await waitFor(() =>
            expect(toast.success).toHaveBeenCalledWith(
                'Student Details Successfully Submited.',
                { autoClose: 2000 }
            )
        );
    });

    it('reports a failure when the student already exists', async () => {
        newStudent.mockRejectedValue({ response: { status: 400 } });
        const { container } = render(<StudentRegisterForm />);
        fillForm();

        submit(container);

        await waitFor(() => expect(toast.error).toHaveBeenCalled());
    });
});
