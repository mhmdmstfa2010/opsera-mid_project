import axios from 'axios';
import api from './students_api';

jest.mock('axios');

describe('students_api', () => {
    const base = 'http://localhost:8080/student/';

    beforeEach(() => {
        jest.clearAllMocks();
        axios.get.mockResolvedValue({ data: {} });
        axios.post.mockResolvedValue({ data: {} });
        axios.put.mockResolvedValue({ data: {} });
        axios.delete.mockResolvedValue({ data: {} });
    });

    it('posts a new student to /new', () => {
        const payload = { firstName: 'Jane' };

        api.studentAPI().newStudent(payload);

        expect(axios.post).toHaveBeenCalledWith(base + 'new', payload);
    });

    it('posts credentials to /authenticate', () => {
        const credentials = { username: 'IT1234', password: 's3cret' };

        api.studentAPI().authenticate(credentials);

        expect(axios.post).toHaveBeenCalledWith(base + 'authenticate', credentials);
    });

    it('gets a single student by business id', () => {
        api.studentAPI().getStudentDataById('IT1234');

        expect(axios.get).toHaveBeenCalledWith(base + 'id/IT1234');
    });

    it('gets every student', () => {
        api.studentAPI().getAllStudents();

        expect(axios.get).toHaveBeenCalledWith(base + 'all');
    });

    it('puts an update to /id/{id}', () => {
        const payload = { firstName: 'Janet' };

        api.studentAPI().updateStudentDataById('IT1234', payload);

        expect(axios.put).toHaveBeenCalledWith(base + 'id/IT1234', payload);
    });

    it('deletes by business id', () => {
        api.studentAPI().deleteStudentDataById('IT1234');

        expect(axios.delete).toHaveBeenCalledWith(base + 'id/IT1234');
    });

    it('honours a custom base url', () => {
        const client = api.studentAPI('https://api.example.com/student/');

        client.getAllStudents();

        expect(axios.get).toHaveBeenCalledWith('https://api.example.com/student/all');
    });
});
