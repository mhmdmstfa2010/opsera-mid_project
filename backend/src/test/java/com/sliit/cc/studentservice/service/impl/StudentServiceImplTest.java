package com.sliit.cc.studentservice.service.impl;

import com.sliit.cc.studentservice.entity.LoginRequest;
import com.sliit.cc.studentservice.entity.Student;
import com.sliit.cc.studentservice.repository.StudentRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class StudentServiceImplTest {

    @Mock
    private StudentRepository studentRepository;

    @InjectMocks
    private StudentServiceImpl studentService;

    private Student sampleStudent() {
        Student student = new Student();
        student.setId("65f0000000000000000000aa");
        student.setFirstName("Jane");
        student.setLastName("Doe");
        student.setStudentId("IT1234");
        student.setEmail("jane@example.com");
        student.setPassword("s3cret");
        return student;
    }

    private LoginRequest loginRequest(String username, String password) {
        LoginRequest request = new LoginRequest();
        request.setUsername(username);
        request.setPassword(password);
        return request;
    }

    @Test
    void create_savesWhenStudentIdAndEmailAreUnused() {
        Student student = sampleStudent();
        when(studentRepository.findByStudentIdOrEmail(student.getStudentId(),
                student.getEmail())).thenReturn(null);
        when(studentRepository.save(any(Student.class))).thenReturn(student);

        assertEquals(student, studentService.create(student));
        verify(studentRepository).save(student);
    }

    @Test
    void create_returnsNullWhenStudentAlreadyExists() {
        Student student = sampleStudent();
        when(studentRepository.findByStudentIdOrEmail(student.getStudentId(),
                student.getEmail())).thenReturn(sampleStudent());

        assertNull(studentService.create(student));
        verify(studentRepository, never()).save(any(Student.class));
    }

    @Test
    void get_returnsTheStudentWithTheGivenId() {
        Student student = sampleStudent();
        when(studentRepository.findById(student.getId()))
                .thenReturn(Optional.of(student));

        assertEquals(student, studentService.get(student.getId()));
    }

    @Test
    void get_propagatesAnExceptionForAnUnknownId() {
        when(studentRepository.findById(anyString())).thenReturn(Optional.empty());

        assertThrows(java.util.NoSuchElementException.class,
                () -> studentService.get("does-not-exist"));
    }

    @Test
    void authenticate_returnsTheStudentWhenThePasswordMatches() {
        Student student = sampleStudent();
        when(studentRepository.findByStudentIdOrEmail("IT1234", "IT1234"))
                .thenReturn(student);

        assertEquals(student,
                studentService.authenticate(loginRequest("IT1234", "s3cret")));
    }

    @Test
    void authenticate_returnsNullWhenThePasswordIsWrong() {
        when(studentRepository.findByStudentIdOrEmail("IT1234", "IT1234"))
                .thenReturn(sampleStudent());

        assertNull(studentService.authenticate(loginRequest("IT1234", "wrong")));
    }

    @Test
    void authenticate_returnsNullWhenTheStudentDoesNotExist() {
        when(studentRepository.findByStudentIdOrEmail("nope", "nope"))
                .thenReturn(null);

        assertNull(studentService.authenticate(loginRequest("nope", "s3cret")));
    }

    @Test
    void getByStudentId_delegatesToTheRepository() {
        Student student = sampleStudent();
        when(studentRepository.findByStudentId("IT1234")).thenReturn(student);

        assertEquals(student, studentService.getByStudentId("IT1234"));
    }

    @Test
    void getAllStudents_returnsEveryStudent() {
        List<Student> all = List.of(sampleStudent());
        when(studentRepository.findAll()).thenReturn(all);

        assertEquals(all, studentService.getAllStudents());
    }

    @Test
    void update_copiesTheMutableFieldsAndSaves() {
        Student existing = sampleStudent();
        Student update = new Student();
        update.setFirstName("Janet");
        update.setLastName("Roe");
        update.setEmail("janet@example.com");
        update.setPassword("n3w");
        when(studentRepository.findByStudentId("IT1234")).thenReturn(existing);
        when(studentRepository.save(any(Student.class))).thenReturn(existing);

        assertTrue(studentService.update("IT1234", update));

        assertEquals("Janet", existing.getFirstName());
        assertEquals("Roe", existing.getLastName());
        assertEquals("janet@example.com", existing.getEmail());
        assertEquals("n3w", existing.getPassword());
        // The business key must survive the update untouched.
        assertEquals("IT1234", existing.getStudentId());
        verify(studentRepository).save(existing);
    }

    @Test
    void delete_removesTheStudentByMongoId() {
        assertTrue(studentService.delete("65f0000000000000000000aa"));

        verify(studentRepository).deleteById("65f0000000000000000000aa");
    }

    @Test
    void deleteByStudentId_removesTheStudentByBusinessId() {
        assertTrue(studentService.deleteByStudentId("IT1234"));

        verify(studentRepository).deleteByStudentId("IT1234");
    }
}
