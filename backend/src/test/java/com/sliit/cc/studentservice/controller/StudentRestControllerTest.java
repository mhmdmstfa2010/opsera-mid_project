package com.sliit.cc.studentservice.controller;

import com.sliit.cc.studentservice.entity.LoginRequest;
import com.sliit.cc.studentservice.entity.Student;
import com.sliit.cc.studentservice.service.StudentService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(StudentRestController.class)
class StudentRestControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private StudentService studentService;

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

    @Test
    void newStudent_returns201AndTheNewIdentifier() throws Exception {
        Student student = sampleStudent();
        when(studentService.create(any(Student.class))).thenReturn(student);

        mockMvc.perform(post("/student/new")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"studentId\":\"IT1234\",\"email\":\"jane@example.com\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value("IT1234"));
    }

    @Test
    void newStudent_returns400WhenTheStudentAlreadyExists() throws Exception {
        when(studentService.create(any(Student.class))).thenReturn(null);

        mockMvc.perform(post("/student/new")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"studentId\":\"IT1234\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.status").value("student already exists."));
    }

    @Test
    void getStudent_returnsTheStudentForTheGivenId() throws Exception {
        when(studentService.get("65f0000000000000000000aa")).thenReturn(sampleStudent());

        mockMvc.perform(get("/student/65f0000000000000000000aa"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.studentId").value("IT1234"))
                .andExpect(jsonPath("$.email").value("jane@example.com"));
    }

    @Test
    void getAllStudents_returnsEveryStudent() throws Exception {
        when(studentService.getAllStudents()).thenReturn(List.of(sampleStudent()));

        mockMvc.perform(get("/student/all"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.length()").value(1))
                .andExpect(jsonPath("$[0].studentId").value("IT1234"));
    }

    @Test
    void getStudentByNumber_returnsTheStudentForTheBusinessId() throws Exception {
        when(studentService.getByStudentId("IT1234")).thenReturn(sampleStudent());

        mockMvc.perform(get("/student/id/IT1234"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.studentId").value("IT1234"));
    }

    @Test
    void authenticateStudent_returnsTheStudentOnSuccess() throws Exception {
        when(studentService.authenticate(any(LoginRequest.class)))
                .thenReturn(sampleStudent());

        mockMvc.perform(post("/student/authenticate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"IT1234\",\"password\":\"s3cret\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.studentId").value("IT1234"));
    }

    @Test
    void authenticateStudent_returns404WhenTheCredentialsAreWrong() throws Exception {
        when(studentService.authenticate(any(LoginRequest.class))).thenReturn(null);

        mockMvc.perform(post("/student/authenticate")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"username\":\"IT1234\",\"password\":\"wrong\"}"))
                .andExpect(status().isNotFound())
                .andExpect(content().string("Student Not Found."));
    }

    @Test
    void updateStudent_reportsSuccess() throws Exception {
        when(studentService.update(anyString(), any(Student.class))).thenReturn(true);

        mockMvc.perform(put("/student/id/IT1234")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"firstName\":\"Janet\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }

    @Test
    void deleteStudent_reportsSuccess() throws Exception {
        when(studentService.deleteByStudentId("IT1234")).thenReturn(true);

        mockMvc.perform(delete("/student/id/IT1234"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true));
    }
}
