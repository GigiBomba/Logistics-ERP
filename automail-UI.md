\# Operion AI Prompt — Design \& Implement the AutoMail UI



\## Objective



Design and implement a \*\*professional, enterprise-grade AutoMail interface\*\* inside Operion.



This prompt is \*\*ONLY\*\* about the AutoMail UI, functionality, workflow and customization. Do \*\*NOT\*\* redesign or modify the Client Manager itself. The Client Manager already exists. Only implement the AutoMail page that is opened from within it.



The AutoMail system should feel comparable to enterprise CRM and ERP software while remaining significantly easier to use.



The primary goal is to automate payment reminder emails while giving users complete control over every aspect of the automation.



\---



\# General Design Philosophy



The AutoMail page should feel like a powerful automation center rather than a simple settings page.



Avoid making the interface look like a collection of checkboxes.



Instead, design it so users immediately understand:



\* what automations exist

\* what emails will be sent

\* when they will be sent

\* who will receive them

\* what the emails contain

\* whether everything is working correctly



The interface should immediately communicate confidence and professionalism.



\---



\# Visual Design



The UI must match Operion's existing visual language.



Requirements:



\* modern

\* spacious

\* elegant

\* rounded cards

\* subtle shadows

\* clean typography

\* consistent spacing

\* clear visual hierarchy



Avoid:



\* clutter

\* tiny settings panels

\* outdated Windows-style interfaces

\* excessive borders

\* unnecessary colors



Use color only where it improves readability.



\---



\# Overall Layout



The AutoMail page should be divided into three primary areas.



\## Left Section



Automation configuration.



This contains:



\* enable/disable automation

\* scheduling

\* delivery rules

\* stop conditions

\* sending options

\* notification preferences



\---



\## Center Section



Automation timeline.



This is the heart of the page.



It should visually show:



\* every scheduled reminder

\* previous reminders

\* upcoming reminders

\* reminder status

\* automation history



The timeline should make it immediately obvious what Operion is going to do next.



\---



\## Right Section



Email editor and live preview.



Users should always be able to see exactly what the email will look like.



The preview should update live.



\---



\# Automation Toggle



At the top of the page:



Large switch:



Enable Automatic Payment Reminders



When disabled:



Entire page becomes visually inactive but still editable.



Users should be able to configure everything before enabling automation.



\---



\# Reminder Schedule



Instead of hardcoding reminder timings, implement a fully customizable reminder schedule.



Users should be able to create an unlimited number of reminder events.



Each reminder event should allow configuring:



\* number of days

\* before or after due date

\* event trigger

\* email template

\* active/inactive



The UI should make adding reminders extremely easy.



Include an obvious:



Add Reminder



button.



\---



\# Reminder Event Card



Each reminder should appear as its own card.



Every card should display:



Trigger



Timing



Template



Status



Actions



Actions:



Edit



Duplicate



Disable



Delete



Reorder



Cards should be draggable so users can reorder reminders.



\---



\# Trigger Types



Support multiple trigger types.



Examples (examples only):



\* Before due date

\* On due date

\* After due date

\* After invoice creation

\* After partial payment

\* Manual trigger



These are examples only.



The implementation should be flexible enough for future expansion.



\---



\# Timeline



The timeline is one of the most important parts of the page.



Display:



Past reminders



Current reminder



Future reminders



Future reminders should appear faded.



Completed reminders should appear completed.



Failed reminders should display failure status.



Cancelled reminders should display cancellation.



The timeline should clearly communicate:



what happened



what is happening



what will happen



without requiring users to open any menus.



\---



\# Reminder Status



Every reminder should display one of several statuses.



Examples (examples only):



Scheduled



Queued



Sending



Sent



Delivered



Opened



Clicked



Failed



Cancelled



Skipped



Payment Received



These are examples only.



The system should support future statuses.



\---



\# Delivery Rules



Allow configuring delivery behavior.



Examples (examples only):



Only send during business hours



Skip weekends



Skip holidays



Delay until next working day



Retry failed emails



Maximum retry attempts



These are examples only.



\---



\# Stop Conditions



Allow configuring exactly when Operion should stop sending reminders.



Examples (examples only):



Payment received



Invoice cancelled



Invoice disputed



Customer blocked



Reminder manually stopped



These are examples only.



\---



\# Email Templates



Users should be able to manage multiple templates.



The template selector should be extremely easy to use.



Support assigning different templates to different reminder events.



Users should never have to duplicate automation just to use another email.



\---



\# Email Editor



The email editor should feel like a professional email editor.



Include:



Subject



Preview text



Body



Signature



Attachments



Formatting toolbar



The editor should support rich text.



\---



\# Variables



Support inserting dynamic variables.



Variables should be inserted using a searchable picker rather than memorizing syntax.



Examples (examples only):



Customer Name



Invoice Number



Due Date



Amount



Currency



Days Overdue



Company Name



Dispatcher Name



Payment Link



Vehicle



Trip Number



Driver



These are examples only.



The variable system should be expandable.



\---



\# Live Preview



The preview should always display exactly how the email will appear.



As users edit the template, the preview updates immediately.



The preview should use realistic sample values.



These values should clearly indicate they are preview data.



\---



\# Attachments



Users should choose which documents are attached automatically.



Examples (examples only):



Invoice PDF



Receipt



CMR



Proof of Delivery



Statement



Custom document



These are examples only.



\---



\# Customer Overrides



Allow overriding automation per customer.



Users should be able to:



disable reminders



change templates



change timing



disable attachments



without affecting global defaults.



\---



\# Presets



Include professionally designed automation presets.



Examples (examples only):



Friendly



Professional



Strict



These are examples only.



Each preset should automatically configure schedules and templates.



Users should still be able to modify everything afterward.



\---



\# Email History



Include a complete history.



Every email should display:



Date



Recipient



Subject



Template used



Status



Delivery information



Opened



Clicked



Attachments



Error (if applicable)



Users should never wonder whether an email was actually sent.



\---



\# Search



Include search functionality.



Users should be able to search:



emails



customers



invoice numbers



templates



statuses



\---



\# Filtering



Support filtering.



Examples (examples only):



Upcoming



Sent



Failed



Opened



Overdue



Cancelled



Manual



Automatic



These are examples only.



\---



\# Statistics



Display useful analytics.



Examples (examples only):



Emails Sent



Open Rate



Click Rate



Bounce Rate



Average Payment Delay



Invoices Recovered



Payments Received After Reminder



These are examples only.



Statistics should be visualized cleanly without overwhelming the interface.



\---



\# Manual Controls



Users should be able to manually:



Send Now



Skip



Pause



Resume



Reschedule



Duplicate



Cancel



Preview



without editing automation rules.



\---



\# Notifications



Allow configuring internal notifications.



Examples (examples only):



Notify dispatcher



Notify accountant



Notify administrator



Notify company owner



These are examples only.



\---



\# Safety



Prevent accidental spam.



Include safeguards such as:



duplicate reminder prevention



maximum reminders per invoice



confirmation before mass sending



retry limits



\---



\# Future Expandability



Design the architecture so future automation types can easily be added.



Examples (examples only):



Trip reminders



CMR reminders



Contract reminders



Maintenance reminders



Driver reminders



Document requests



Customer follow-ups



These are examples only.



Do not hardcode the UI specifically around invoices.



\---



\# User Experience



The interface should feel effortless.



Users should understand the workflow within seconds.



Configuration should require minimal clicks.



Everything should be searchable.



Everything should be logically grouped.



Everything should provide immediate visual feedback.



Advanced settings should remain accessible without cluttering the interface.



The AutoMail page should become one of Operion's flagship quality-of-life features and should feel significantly more polished and user-friendly than the equivalent functionality found in traditional ERP systems.



