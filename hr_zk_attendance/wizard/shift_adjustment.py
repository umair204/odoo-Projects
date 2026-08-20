from datetime import timedelta,datetime, date, time
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError, RedirectWarning
import logging
import pytz


class ShiftAdjustment(models.TransientModel):
    _name = 'shift.adjustment'
    _description = 'Shift Adjustment'

    employee_id = fields.Many2one('hr.employee', 'Employee' ,required=True )
    manager_id = fields.Many2one(related='employee_id.parent_id', string='Manager')
    avatar_1920 = fields.Image("Avatar", max_width=128, max_height=128, compute='_compute_avatar_128')
    position_id = fields.Many2one(related='employee_id.job_id', string='Job Position')
    department_id = fields.Many2one(related='employee_id.department_id', string='Department')
    shift_id = fields.Many2one('employee.shift', string='New Shift', required=True,)
    start_date = fields.Date('Start Date', readonly=False)
    end_date = fields.Date('End Date', readonly=False)
    rest_days_ids = fields.Many2many('hr.rest_day', string='Rest Days', compute='_compute_rest_days', store = True, readonly = False)


    attendance_line_ids = fields.One2many('shift.adjustment.lines', 'shift_adjustment_id', compute="action_fetch_shift_data" ,string='Attendance Lines')
    lines_count = fields.Integer(compute='_compute_lines_count', default=0,  string='Lines Count')

    adjustment_type = fields.Selection(
        [
            ('adjust_shift', 'Adjust Shift'),
            ('unrecorded_attendance', 'Unrecorded Attendance'),
        ],
        string='Adjustment Type',
        required=True,
    )


    # @api.model
    # def get_model_fields(self):
    #     model_fields = self.env['ir.model.fields'].search([
    #         ('model_id.model', '=', 'hr.contract'),('ttype','in', ['float']),
    #     ])
    #
    #     return [(field.name, field.field_description) for field in model_fields]
    #
    # selected_field = fields.Selection(
    #     selection='get_model_fields',
    #     string='Selected Field'
    # )


    @api.depends('employee_id')
    def _compute_rest_days(self):
        for rec in self:
            data = rec.employee_id.rest_days_ids
            rec.write({'rest_days_ids': [(6, 0, data.ids)]})


    @api.depends('attendance_line_ids')
    def _compute_lines_count(self):
        for rec in self:
            rec.lines_count = len(rec.attendance_line_ids)

    @api.depends('employee_id')
    def _compute_avatar_128(self):
        for rec in self:
            rec.avatar_1920 = rec.employee_id.image_1920

    # For Populating attendance Lines
    @api.depends('start_date', 'end_date', 'employee_id',)
    def action_fetch_shift_data(self):
        lines = []
        self.attendance_line_ids = [(5, 0, 0)]  # Unlink old Records
        if self.employee_id and self.start_date and self.end_date:
            hr_attendance_data = self.env['hr.attendance'].search(
                [('employee_id', '=', self.employee_id.id),
                 ('current_shift_att_date', '>=', self.start_date),
                 ('current_shift_att_date', '<=', self.end_date)])
            for data in hr_attendance_data:
                lines.append(
                    (0, 0, {
                        'employee_id': data.employee_id.id,
                        'check_in': data.check_in,
                        'check_out': data.check_out,
                        'employee_shift_id': data.employee_id.employee_shift_id.id,
                        'check_in_status': data.check_in_status,
                        'check_out_status': data.check_out_status,
                    }
                     ))
            self.attendance_line_ids = lines

    def float_time_to_exact_time(self, float_time_):
        # Extract hours
        hours = int(float_time_)
        # Extract minutes and seconds from the fractional part
        fractional_part = float_time_ - hours
        minutes = int(fractional_part * 60)
        seconds = int(round((fractional_part * 60 - minutes) * 60))
        # Format the time string
        return f'{hours:02}:{minutes:02}:{seconds:02}'

    def float_to_time(self, float_hours):
        # Extract hours and minutes from the float
        hours = int(float_hours)
        minutes = int((float_hours - hours) * 60)
        return time(hours, minutes)


    def float_time_to_exact_time_combine(self, float_time_):
        # Extract hours
        hours = int(float_time_)
        # Extract minutes and seconds from the fractional part
        fractional_part = float_time_ - hours
        minutes = int(fractional_part * 60)
        seconds = int(round((fractional_part * 60 - minutes) * 60))
        # Format the time string
        return [hours,minutes,seconds]

    def get_day_of_week(self, date_time_):
        day = date_time_.strftime('%A')
        return day
    # Not being used for now
    def datetime_difference_in_minutes(self,start_datetime, end_datetime):
        if start_datetime > end_datetime:
            raise ValueError("start_datetime must be less than or equal to end_datetime")
        delta = end_datetime - start_datetime
        # Convert the difference from timedelta to minutes
        difference_in_minutes = delta.total_seconds() / 60.0

        return difference_in_minutes

    # For converting datetime to float time
    def datetime_to_float_time(self, datetime_):
        # Extract hours, minutes, and seconds from the datetime object
        hours = datetime_.hour
        minutes = datetime_.minute
        seconds = datetime_.second
        # Convert to float where the time is represented as HH.MMSS
        float_time = hours + minutes / 60.0 + seconds / 3600.0
        return float_time


    def action_reset(self):
        self.start_date = False
        self.end_date = False
        self.attendance_line_ids = [(5, 0, 0)]
        message = f'Shift Adjustment has been reset. No changes have been made.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _('Info'),
                'message': _(message),
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }}

    def draft_attendance_record(self, employee_id, department_id, shift_id, check_in_datetime, check_out_datetime, current_date):
        attendance_record = {
            'employee_id': employee_id,
            'check_in': check_in_datetime,
            'check_out': check_out_datetime,
            'check_in_status': 'presentontime',
            'check_out_status': 'presentontime',
            'late_time': None,
            'early_time': None,
            'status_leave': None,
            'department_id': department_id,
            'employee_shift_id': shift_id,
            'current_shift_att_date': current_date,
        }
        return attendance_record



    def action_adjust_now(self):

        if not self.shift_id:
            raise UserError("Please select a shift.")

        elif not self.start_date or not self.end_date:
            raise UserError("Please select a date range.")

        elif self.adjustment_type == 'adjust_shift' and len(self.attendance_line_ids) == 0:
            raise UserError("No Attendance Data Found for the selected Employee in this date range.")

        elif self.employee_id and self.start_date and self.end_date and self.shift_id and self.adjustment_type == 'adjust_shift':
            # initializing local variables
            check_in, check_out,early_out, check_in_status, check_out_status, rest_days_= 0, 0, 0, '', '', []

            # Calculating Early Out
            early_out = self.shift_id.short_leave - self.shift_id.shift_start

            # Initializing Rest Days
            if self.rest_days_ids:
                rest_days_ = self.rest_days_ids.mapped('name')

            # Fetching Attendance Data
            hr_attendance_data = self.env['hr.attendance'].search(
                [('employee_id', '=', self.employee_id.id),
                 ('current_shift_att_date', '>=', self.start_date),
                 ('current_shift_att_date', '<=', self.end_date)])

            # for data in hr_attendance_data:
            #     s_start_date = self.de
            #     # Adjusting check-in and check-out times based on backend night shift logic
            #     shift_start_date = datetime.combine(data.current_shift_att_date, self.shift_id.shift_start)
            #     shift_end_date = datetime.combine(data.current_shift_att_date, self.shift_id.shift_end)
            #     print("_________________________________")
            #     print(self.shift_start_date)
            #     print(self.shift_end_date)
            #     print("_________________________________")
            #
            #     # Handle night shift spanning two days
            #     if self.shift_id.shift_type == 'Night':  # Assuming 'is_night_shift' is a field or logic that checks if the shift spans midnight
            #         if shift_end_date <= shift_start_date:
            #             shift_end_date += timedelta(days=1)
            #
            #     check_in_time = data.check_in
            #     check_out_time = data.check_out
            #
            #     # Adjusting for shifts that start before and end after the shift window
            #     if check_in_time < shift_start_date:
            #         check_in_time = shift_start_date
            #     if check_out_time > shift_end_date:
            #         check_out_time = shift_end_date
            #
            #     check_in = self.datetime_to_float_time(check_in_time + timedelta(hours=5))
            #     check_out = self.datetime_to_float_time(check_out_time + timedelta(hours=5))
            #     late_minutes, early_minutes = 0, 0
            #
            #     # Checking Check-In Status and late minutes
            #     if check_in <= (self.shift_id.shift_start + self.shift_id.margin):
            #         check_in_status = 'presentontime'
            #     elif (self.shift_id.shift_start + self.shift_id.margin) < check_in <= self.shift_id.late_end:
            #         check_in_status = 'late'
            #         late_minutes = check_in - self.shift_id.shift_start
            #     elif self.shift_id.late_end < check_in <= self.shift_id.short_leave:
            #         check_in_status = 'shortleave'
            #     elif check_in > self.shift_id.short_leave:
            #         check_in_status = 'absent'
            #     else:
            #         if not check_in:
            #             check_in_status = 'absent'
            #
            #     # Checking Check-Out Status
            #     if check_out >= (self.shift_id.shift_end - self.shift_id.margin):
            #         check_out_status = 'presentontime'
            #     elif early_out >= (self.shift_id.shift_end - check_out) and check_out <= (
            #             self.shift_id.shift_end - self.shift_id.margin):
            #         early_minutes = self.shift_id.shift_end - check_out
            #         check_out_status = 'shortleave'
            #     elif check_out <= (self.shift_id.shift_end - self.shift_id.margin):
            #         check_out_status = 'absent'
            #     else:
            #         if not check_out:
            #             check_out_status = 'absent'
            #
            #     # converting float time to exact time
            #     late_minutes = self.float_time_to_exact_time(late_minutes)
            #     early_minutes = self.float_time_to_exact_time(early_minutes)
            #
            #     # Calculating the Rest Days
            #     current_day = self.get_day_of_week(data.current_shift_att_date)
            #
            #     if self.rest_days_ids and current_day in rest_days_:
            #         check_in_status = 'restday'
            #         check_out_status = 'restday'
            #         late_minutes = '00:00:00'
            #         early_minutes = '00:00:00'
            #
            #     # Updating Attendance Data
            #     data.sudo().write({
            #         'check_in_status': check_in_status,
            #         'check_out_status': check_out_status,
            #         'employee_shift_id': self.shift_id.id,
            #         'late_time': late_minutes if late_minutes != '00:00:00' else None,
            #         'early_time': early_minutes if early_minutes != '00:00:00' else None,
            #     })
            #
            # message = f'Attendance adjustment completed successfully. {self.lines_count} records were updated.'
            # return {
            #     'type': 'ir.actions.client',
            #     'tag': 'display_notification',
            #     'params': {
            #         'type': 'success',
            #         'title': _('Successful'),
            #         'message': _(message),
            #         'sticky': True,
            #         'next': {'type': 'ir.actions.act_window_close'},
            #     }}

            for data in hr_attendance_data:

                #To avoid multiple check_in and check_out addition with time difference
                check_in = self.datetime_to_float_time(data.check_in + timedelta(hours=5))
                check_out = self.datetime_to_float_time(data.check_out + timedelta(hours=5))
                late_minutes, early_minutes = 0, 0

                # Checking Check-In Status and late minutes
                if check_in <= (self.shift_id.shift_start + self.shift_id.margin):
                    check_in_status = 'presentontime'
                elif (self.shift_id.shift_start + self.shift_id.margin) < check_in <= self.shift_id.late_end:
                    check_in_status = 'late'
                    late_minutes = check_in - self.shift_id.shift_start
                elif self.shift_id.late_end < check_in <= self.shift_id.short_leave:
                    check_in_status = 'shortleave'
                elif check_in > self.shift_id.short_leave:
                    check_in_status = 'absent'
                else:
                    if not check_in:
                        check_in_status = 'absent'


                # Checking Check-Out Status
                if check_out >= (self.shift_id.shift_end - self.shift_id.margin):
                    check_out_status = 'presentontime'
                elif early_out >= (self.shift_id.shift_end - check_out) and  check_out <= (self.shift_id.shift_end - self.shift_id.margin):
                    early_minutes = self.shift_id.shift_end - check_out
                    check_out_status = 'shortleave'
                elif check_out <= (self.shift_id.shift_end - self.shift_id.margin):
                    check_out_status = 'absent'
                else:
                    if not check_out:
                        check_out_status = 'absent'


                # converting float time to exact time
                late_minutes = self.float_time_to_exact_time(late_minutes)
                early_minutes = self.float_time_to_exact_time(early_minutes)


                # Calculating the Rest Days
                current_day = self.get_day_of_week(data.current_shift_att_date)

                if self.rest_days_ids and  current_day in rest_days_:
                    check_in_status = 'restday'
                    check_out_status = 'restday'
                    late_minutes = '00:00:00'
                    early_minutes = '00:00:00'
                    data.is_rest_day = True


                #  Updating Attendance Data
                data.sudo().write({
                    'check_in_status': check_in_status,
                    'check_out_status': check_out_status,
                    'employee_shift_id': self.shift_id.id,
                    'late_time': late_minutes if late_minutes != '00:00:00' else None,
                    'early_time': early_minutes if early_minutes != '00:00:00' else None,
                })

        elif self.employee_id and self.start_date and self.end_date and self.shift_id and self.adjustment_type == 'unrecorded_attendance':
            # initializing local variables
            check_in, check_out,early_out, check_in_status, check_out_status, rest_days_, missed_list= 0, 0, 0, '', '', [], []

            # Calculating Early Out
            early_out = self.shift_id.short_leave - self.shift_id.shift_start

            # Initializing Rest Days
            if self.rest_days_ids:
                rest_days_ = self.rest_days_ids.mapped('name')

            # Fetching Shift Details
            # Subtract 5 hours

            shift_start_time_ = self.float_to_time(abs(self.shift_id.shift_start - 5.0))
            shift_end_time_ = self.float_to_time(abs(self.shift_id.shift_end - 5.0))


            # Calculating Attendance Data
            current_date = self.start_date
            while current_date <= self.end_date:
                check_in_datetime = datetime.combine(current_date, shift_start_time_)
                check_out_datetime = datetime.combine(current_date, shift_end_time_)

                #rest_day check
                current_day = self.get_day_of_week(current_date)
                if current_day not in rest_days_:
                    # Create an attendance record
                    missed_list.append(
                        self.draft_attendance_record(self.employee_id.id, self.employee_id.department_id.id,
                                                     self.shift_id.id, check_in_datetime, check_out_datetime,
                                                     current_date))
                 # Move to the next date
                current_date += timedelta(days=1)

            res = self.env['hr.attendance'].sudo().create(missed_list)

        message = f'Unrecorded Attendance completed successfully. {self.lines_count} new records were created.'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'title': _('Successful'),
                'message': _(message),
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            }}



class AttendanceLines(models.TransientModel):
    _name = "shift.adjustment.lines"
    _description = "Attendance Lines"

    shift_adjustment_id = fields.Many2one(
        "shift.adjustment",
        "Shift Adjustment",
        index=True,)

    employee_id = fields.Many2one(
        "hr.employee",
        "Employee")

    check_in_status = fields.Selection(
        [
            ("presentontime", "Present"),
            ("late", "Late"),
            ("shortleave", "Short Leave"),
            ("halfleave", "Half Leave"),
            ("restday", "Rest Day"),
            ("paidleave", "Paid Leave"),
            ("unpaidleave", "Unpaid Leave"),
            ("casualleave", "Casual Leave"),
            ("sickleave", "Sick Leave"),
            ("compensatoryleave", "Compensatory Leave"),
            ("gazetteleave", "Gazette Leave"),
            ("officialleaves", "Official Leave"),
            ("workfromhome", "Work from Home"),
            ("outdoorduty", "Outdoor Duty"),
            ("absent", "Absent"),
        ],
        "Check In Status",)

    check_out_status = fields.Selection(
        [
            ("presentontime", "Present"),
            ("late", "Late"),
            ("shortleave", "Short Leave"),
            ("halfleave", "Half Leave"),
            ("restday", "Rest Day"),
            ("paidleave", "Paid Leave"),
            ("unpaidleave", "Unpaid Leave"),
            ("casualleave", "Casual Leave"),
            ("sickleave", "Sick Leave"),
            ("compensatoryleave", "Compensatory Leave"),
            ("gazetteleave", "Gazette Leave"),
            ("officialleaves", "Official Leave"),
            ("workfromhome", "Work from Home"),
            ("outdoorduty", "Outdoor Duty"),
            ("absent", "Absent"),
        ],
        "Check Out Status", )

    employee_shift_id = fields.Many2one(
        "employee.shift",
        "Employee Shift" )

    check_in = fields.Datetime(
        "Check In",
    )
    check_out = fields.Datetime(
        "Check Out",
    )







