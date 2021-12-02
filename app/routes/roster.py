from re import S
from app import app
from .users import credentials_to_dict
from flask import render_template, redirect, session, flash, url_for, Markup
from app.classes.data import User, GoogleClassroom
from app.classes.forms import SimpleForm, SortOrderCohortForm
from datetime import datetime as dt
import mongoengine.errors
import google.oauth2.credentials
import googleapiclient.discovery
from google.auth.exceptions import RefreshError
import ast

@app.route("/roster/<gclassid>", methods=['GET','POST'])
def roster(gclassid):
    gclass = GoogleClassroom.objects.get(gclassid=gclassid)
    for stu in gclass.groster['roster']:
        print(f"cohort: {stu['sortCohort']} updateGClass: {stu['updateGClasses']}")

    try:
        otdstus = gclass.groster['roster']
    except:
        flash(Markup(f"You need to <a href='/getroster/{gclassid}'>update your roster from Google Classroom</a>."))
        return redirect(url_for('checkin'))

    otdstus = sorted(otdstus, key = lambda i: (i['sortCohort'],i['profile']['name']['fullName']))
   
    return render_template('rosternew.html',gclassname=gclass.gclassdict['name'], gclassid=gclassid, otdstus=otdstus)


@app.route("/getroster/<gclassid>", methods=['GET','POST'])
def getroster(gclassid):
   
    # TODO 
    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect('/authorize')    
    session['credentials'] = credentials_to_dict(credentials)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)
    gstudents = []
    pageToken = None
    try:
        students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
    except RefreshError:
        flash("When I asked for the courses from Google Classroom I found that your credentials needed to be refreshed.")
        return redirect('/authorize')

    while True:
        pageToken = students_results.get('nextPageToken')
        gstudents.extend(students_results['students'])
        if not pageToken:
            break
        students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()

    stus=[]
    length = len(gstudents)
    for i,stu in enumerate(gstudents):
        # Make sure the students are actually students
        if stu['profile']['emailAddress'][:2]=="s_":   
            stu['sortCohort'] = '--'         
            try:
                # see if they are in OTData
                otdstu = User.objects.get(otemail=stu['profile']['emailAddress'])
            except mongoengine.errors.DoesNotExist as error:
                flash(f"{stu['profile']['name']['fullName']} is not in OTData")
            except Exception as error:
                flash(f"Error occured when looking for {stu['profile']['name']['fullName']}: {error}")
            else:
                stu['otdobject'] = otdstu

            try:
                otdStuClass = otdstu.gclasses.get(gclassid=gclassid)
            except mongoengine.errors.DoesNotExist as error:
                stu['updateGClasses'] = "True"
            except Exception as error:
                flash(f"An unknown error occured: {error}")
            else:
                stu['updateGClasses'] = "False"
                try:
                    if otdStuClass.sortcohort:
                        stu['sortCohort'] = otdStuClass.sortcohort
                except KeyError:
                    pass
            print(f"{i}/{length} sort cohort: {stu['sortCohort']} updateGClass: {stu['updateGClasses']}")
            stus.append(stu)
    
    stus = sorted(stus, key = lambda i: (i['sortCohort'],i['profile']['name']['familyName']))

    groster = {}
    groster['roster'] = stus
    gclass = GoogleClassroom.objects.get(gclassid=gclassid)
    #gclassname = gclass.gclassdict['name']
    gclass.update(
            groster = groster
        )
    return redirect(url_for('roster',gclassid=gclassid))
    #return render_template('roster.html',gclassname=gclassname, gclassid=gclassid, otdstus=stus)

@app.route('/getguardians/<gclassid>/<index>')
@app.route('/getguardians/<gclassid>')
def getgaurdians(gclassid,index=0):
    if index == 0:
        session['tempGStudents'] = None

    # startIterationTime = dt.now()
    index=int(index)

    # get the roster
    # iterate through each student and check if they have gaurdian 
    # if they don't have a gaurdian get the parent email and send invite
    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect('/authorize')    
    
    session['credentials'] = credentials_to_dict(credentials)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)

    try:
        session['tempGStudents']
    except:
        session['tempGStudents'] = []

    if not session['tempGStudents'] or len(session['tempGStudents'])==0:
        gstudents = []
        pageToken = None
        #students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
        try:
            students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
        except RefreshError:
            flash("When I asked for the courses from Google Classroom I found that your credentials needed to be refreshed.")
            return redirect('/authorize')

        while True:
            pageToken = students_results.get('nextPageToken')
            gstudents.extend(students_results['students'])
            if not pageToken:
                break
            students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
        session['tempGStudents'] = gstudents

    # Remove students without s_ at the beginning of their address
    studentsOnly=[]
    for student in session['tempGStudents']:
        if student['profile']['emailAddress'][:2] == 's_':
            studentsOnly.append(student)

    session['tempGStudents'] = studentsOnly
    
    numStus = len(session['tempGStudents'])  
    numIterations = 4
    iterator = 0

    for student in session['tempGStudents'][index:]:
        # check for gaurdians
        guardians = classroom_service.userProfiles().guardians().list(studentId=student['userId']).execute()
        # see if the student is in OTData
        try:
            editStu = User.objects.get(otemail=student['profile']['emailAddress'])
        except:
            editStu = False
            flash(f"{student['profile']['emailAddress']} is not in OTData.")
        # if the student is in OTData AND has gaurdians, update the record
        if guardians and editStu:
                editStu.update(
                    gclassguardians = guardians
                )
        # Now check for invites      
        try:
            invites = classroom_service.userProfiles().guardianInvitations().list(studentId = student['userId']).execute()
        except:
            flash(f"Gaurdian invites failed for GID: {student['profile']['emailAddress']}.")

        if invites and editStu:
            editStu.update(
                gclassguardianinvites = invites
            )
        try: 
            numGuardians = len(guardians['guardians'])
        except:
            numGuardians = 0

        try:
            numInvites = len(invites['guardianInvitations'])
        except:
            numInvites = 0

        flash(f"{index+1}/{numStus}: {student['profile']['emailAddress']} Guardians: {numGuardians} Invites: {numInvites}")
        index = index + 1
        iterator = iterator + 1
        if iterator == numIterations:
            break

    if numStus > (index):
        # This is the url for the loading page to call back
        url = f"/getguardians/{gclassid}"

        return render_template ('loading.html', url=url, nextIndex=index, total=numStus)

    session['tempGStudents'] = None
    return redirect(url_for('roster',gclassid=gclassid))

@app.route('/inviteguardians/<gid>/<gclassid>/<gclassname>')
@app.route('/inviteguardians/<gid>')
def inviteguardians(gid,gclassid=None,gclassname=None):
    try:
        editStu = User.objects.get(gid=gid)
    except:
        editStu = False

    inviteEmails = []

    if editStu.adults:
        for adult in editStu.adults:
            inviteEmails.append(adult.email)
    elif editStu.aadultemail:
        inviteEmails.append(editStu.aadultemail)
    
    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect('/authorize')    
    
    session['credentials'] = credentials_to_dict(credentials)
    service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)
    
    for inviteEmail in inviteEmails:
        guardianInvitation = {'invitedEmailAddress': inviteEmail}
        try:
            # TODO check the error msg to be sure it is cause it already exists
            guardianInvitation = service.userProfiles().guardianInvitations().create(
                                    studentId=editStu.otemail, 
                                    body=guardianInvitation
                                ).execute()
        except Exception as error:
            flash(f"Error: {error}")
            flash(f"Invite already exists for {inviteEmail}.")

    invites = service.userProfiles().guardianInvitations().list(studentId = gid).execute()
    if invites:
        editStu.update(
            gclassguardianinvites = invites
        )

    if gclassid and gclassname:
        return redirect(url_for('roster',gclassid=gclassid,gclassname=gclassname))
    else:
        return(redirect(url_for('profile',aeriesid=editStu.aeriesid)))



def getCourseWork(gclassid):
    pageToken = None
    assignmentsAll = {}
    assignmentsAll['courseWork'] = []

    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect('/authorize')    
    
    session['credentials'] = credentials_to_dict(credentials)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)

    # TODO get all assignments and add as dict to gclassroom record
    while True:
        try:
            assignments = classroom_service.courses().courseWork().list(
                    courseId=gclassid,
                    pageToken=pageToken,
                    ).execute()
        except RefreshError:
            return "refresh"

        except Exception as error:
            x, y = error.args     # unpack args
            if isinstance(y, bytes):
                y = y.decode("UTF-8")
            errorDict = ast.literal_eval(y)
            if errorDict['error'] == 'invalid_grant':
                flash('Your login has expired. You need to re-login.')
                return "refresh"
            elif errorDict['error']['status'] == "PERMISSION_DENIED":
                return "refresh"
            else:
                flash(f"Got unknown Error: {errorDict}")
                return False

        try: 
            assignmentsAll['courseWork'].extend(assignments['courseWork'])
        except (KeyError,UnboundLocalError):
            break
        else:
            pageToken = assignments.get('nextPageToken')
            if pageToken == None:
                break
    gclassroom = GoogleClassroom.objects.get(gclassid=gclassid)
    gclassroom.update(courseworkdict = assignmentsAll)
    return True

@app.route('/getcoursework/<gclassid>')
def getcw(gclassid):
    result = getCourseWork(gclassid)
    if result == "refresh":
        return redirect(url_for('authorize'))
    return redirect(url_for('checkin'))

@app.route('/listmissing/<gclassid>/<index>')
@app.route('/listmissing/<gclassid>')
def nummissing(gclassid,index=0):
    index=int(index)

    gclass = GoogleClassroom.objects.get(gclassid=gclassid)
    gclassname = gclass.gclassdict['name']

    if google.oauth2.credentials.Credentials(**session['credentials']).valid:
        credentials = google.oauth2.credentials.Credentials(**session['credentials'])
    else:
        return redirect('/authorize')    
    
    session['credentials'] = credentials_to_dict(credentials)
    classroom_service = googleapiclient.discovery.build('classroom', 'v1', credentials=credentials)

    if index == 0:
        session['startTimeTemp'] = dt.now()

    try:
        session['tempGStudents']
    except:
        session['tempGStudents'] = None
        session['startTimeTemp'] = dt.now()

    if not session['tempGStudents']:
        gstudents = []
        pageToken = None
        try:
            students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()
        except RefreshError:
            flash("When I asked for the courses from Google Classroom I found that your credentials needed to be refreshed.")
            return redirect('/authorize')

        while True:
            pageToken = students_results.get('nextPageToken')
            gstudents.extend(students_results['students'])
            if not pageToken:
                break
            students_results = classroom_service.courses().students().list(courseId = gclassid,pageToken=pageToken).execute()

        session['tempGStudents'] = gstudents

    # Remove students without s_ at the beginning of their address
    gStudentsOnly=[]
    for gStudent in session['tempGStudents']:
        if gStudent['profile']['emailAddress'][:2] == 's_':
            gStudentsOnly.append(gStudent)

    session['tempGStudents'] = gStudentsOnly
    
    numStus = len(session['tempGStudents'])  
    # How many loops to make before sending to loading page
    numIterations = 4

    for gstudent in session['tempGStudents'][index:index+numIterations]:
        index=index+1

        # See if student exists in OTData
        try:
            otdStudent = User.objects.get(gid = gstudent['userId'])
        except:
            flash(f"{gstudent['profile']['emailAddress']} is not in OTData.")
            otdStudent = None

            try:
                otdStudentClass = otdStudent.gclasses.get(gclassid = gclassid)
            except:
                otdStudentClass = None
                flash(f"Failed to find {gclassname} in {otdStudent.fname}'s OTData gclasses.")
            
            if otdStudent and otdStudentClass:
                flash(f"{otdStudent.fname} {otdStudent.alname}")
    
    if numStus > index:
        # elapsedTime = dt.now() - session['startTimeTemp']
        # # an approximation of how much time it took to process one student
        # currPerStuTime = elapsedTime / index
        # timeLeft = (numStus - (index+1)) * currPerStuTime
        return render_template ('loading.html', nextIndex=index, total=numStus)


    session['tempGStudents'] = None
    return redirect(url_for('roster',gclassid=gclassid))



@app.route('/assignments/list/<aeriesid>')
def missingassignmentslist(aeriesid):
    stu = User.objects.get(aeriesid=aeriesid)
    for gclass in stu.gclasses:
        # if gclass.missingasses:
        #     for missingAss in gclass.missingasses:
        #         if missingAss in 
        # update the assignment list if there is none
        if gclass.status and gclass.status.lower() == "active":
            getCourseWorkResult = getCourseWork(gclass.gclassid)
            print(f"Result: {getCourseWorkResult}")
            if getCourseWorkResult == "AUTHORIZE":
                return redirect(url_for('authorize'))
            elif getCourseWorkResult == "PERMISSION_DENIED":
                flash(f"You do not have permission to access {gclass.gclassroom.gclassdict['name']} for this student.")
            elif not getCourseWorkResult:
                flash(f"An error occured. I was unable to update the assignment list for {gclass.gclassroom.gclassdict['name']}.")
            elif getCourseWorkResult:
                flash(f"Saved assignment list for {gclass.gclassroom.gclassdict['name']}")

    return render_template('missasslist.html.j2',stu=stu)

@app.route('/rostersort/<gclassid>/<sort>', methods=['GET', 'POST'])
@app.route('/rostersort/<gclassid>', methods=['GET', 'POST'])
def editrostersortorder(gclassid,sort=None):

    gclassroom = GoogleClassroom.objects.get(gclassid=gclassid)
    if sort:
        rosterToSort = gclassroom.groster['roster']
        rosterToSort = sorted(rosterToSort, key = lambda i: (i['sortCohort'], i['profile']['name']['familyName']))
        groster = {}
        groster['roster'] = rosterToSort
        gclassroom.update(
            groster=groster
        )
    else:
        groster = gclassroom.groster

    sortForms={}
    form=SortOrderCohortForm()

    if form.validate_on_submit():
        #otStudent = User.objects.get(gid = form.gid.data)
        otStudent = User.objects.get(otemail = form.gmail.data)

        try:
            otStudent.gclasses.get(gclassid = form.gclassid.data)
        except mongoengine.errors.DoesNotExist:
            flash(f"{otStudent.fname} {otStudent.alname} does not have this class in their classes list.")
        else:
            otStudent.gclasses.filter(gclassid = form.gclassid.data).update(
                sortcohort = form.sortOrderCohort.data
            )
            otStudent.save()

            gclassroom.groster['roster'][int(form.order.data)]['sortCohort'] = form.sortOrderCohort.data
            gclassroom.update(
                groster = gclassroom.groster
            )
            #groster = gclassroom.groster
            rosterToSort = gclassroom.groster['roster']
            rosterToSort = sorted(rosterToSort, key = lambda i: (i['sortCohort'], i['profile']['name']['familyName']))
            groster = {}
            groster['roster'] = rosterToSort
            gclassroom.update(
                groster=groster
            )



    for i in range(len(groster['roster'])):

        try:
            sortOrderCohort = groster['roster'][i]['sortCohort']
        except KeyError:
            sortOrderCohort = None

        sortForms['form'+str(i)]=SortOrderCohortForm()
        sortForms['form'+str(i)].gid.data = groster['roster'][i]['userId']
        sortForms['form'+str(i)].gmail.data = groster['roster'][i]['profile']['emailAddress']
        sortForms['form'+str(i)].gclassid.data = groster['roster'][i]['courseId']
        sortForms['form'+str(i)].sortOrderCohort.data = sortOrderCohort
        if gclassroom.sortcohorts:
            choices = []
            for choice in gclassroom.sortcohorts:
                choices.append((choice,choice))
            sortForms['form'+str(i)].sortOrderCohort.choices = choices
        sortForms['form'+str(i)].order.data = i

    numForms = len(sortForms)

    return render_template('rostersortform.html.j2',gclassroom=gclassroom,forms=sortForms,numForms=numForms,groster=groster)

@app.route('/sortcohorts/<gcid>', methods=['GET','POST'])
def sortcohorts(gcid):

    googleClassroom = GoogleClassroom.objects.get(gclassid=gcid)

    form = SimpleForm()

    if form.validate_on_submit():
        cohorts = form.field.data
        sortCohorts = cohorts.split(',')
        googleClassroom.update(sortcohorts=sortCohorts)
        return redirect(url_for('editrostersortorder',gclassid=gcid))

    googleClassroom.reload()

    if googleClassroom.sortcohorts:
        form.field.data = ','.join(googleClassroom.sortcohorts)
        print(googleClassroom.sortcohorts)
        print(form.field.data)

    return render_template('sortcohorts.html',form=form,googleClassroom=googleClassroom)
    
