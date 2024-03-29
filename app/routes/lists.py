from flask.helpers import url_for
from werkzeug.utils import redirect
from app import app

from flask import render_template, flash, Markup, session, request
from app.classes.data import User, Group, Role
from app.classes.forms import ListQForm, SimpleForm, GroupsForm, GroupMsgForm
from .msgs import txtGroupFunc
from mongoengine import Q
from .users import formatphone
import datetime as dt
from flask_login import current_user

@app.route('/listq/<nomap>', methods=['GET', 'POST'])
@app.route('/listq', methods=['GET', 'POST'])

def listq(nomap=0):

    form = ListQForm()

    studentOBJ = Role.objects.get(name='student')
    teacherOBJ = Role.objects.get(name='teacher')

    grades = User.objects(roles__icontains=studentOBJ).distinct(field="grade")
    gradeslist = []
    for grade in grades:
        if grade > 0:
            gradeslist.append((str(grade),str(grade)))

    genders = User.objects(roles__icontains=studentOBJ).distinct(field="agender")
    genderslist = []
    for gender in genders:
        if len(gender) > 0:
            genderslist.append((gender,gender))

    advisors = User.objects(roles__icontains=studentOBJ).distinct(field="advisor")
    advisorslist = []
    for adv in advisors:
        if len(adv) > 0:
            advisorslist.append((adv,adv))
    advisorslist.insert(0,('','-----'))

    form.grade.choices = gradeslist
    form.gender.choices = genderslist
    form.advisor.choices = advisorslist
    if form.validate_on_submit():

        if len(form.grade.data) > 0:
            gradequery="("
            for i,grade in enumerate(form.grade.data):
                gradequery = gradequery + f"Q(grade='{grade}')"
                if i < len(form.grade.data) - 1:
                    gradequery = gradequery + ' | '
                else:
                    gradequery = gradequery + ' ) '
        else:
            gradequery = '(Q(oemail__exists = True))'

        if len(form.gender.data) > 0:
            genderquery="("
            for i,gender in enumerate(form.gender.data):
                genderquery = genderquery + f"Q(agender='{gender}')"
                if i < len(form.gender.data) - 1:
                    genderquery = genderquery + ' | '
                else:
                    genderquery = genderquery + ' ) '
        else:
            genderquery = '(Q(oemail__exists = True))'

        if len(form.advisor.data) > 0:
            advisorquery = (Q(advisor = form.advisor.data))
        else:
            advisorquery = Q(oemail__exists = True)
        isstudentquery = Q(roles__icontains=studentOBJ)

        users = User.objects(eval(gradequery) & eval(genderquery) & advisorquery & isstudentquery)
        for user in users:
            siblings = User.objects(afamkey = user.afamkey)
            if len(siblings) > 0:
                user.siblings = siblings

        if form.results.data == "map":
            return render_template('usermap.html',users=users)
        else:
            return render_template('studentlistform.html',form=form, users=users, total=len(users))
    return render_template('studentlistform.html',form=form, users=None, total=None)


@app.route('/usermap')
def usermap():
    users=User.objects()
    return render_template('usermap.html',users=users)


@app.route('/logins')
def logins():
    logins = User.objects(lastlogin__gt = dt.datetime(2020,1,1)).order_by('lastlogin')
    flash("All Logins.")
    return render_template('logins.html',logins=logins)

@app.route('/edits')
def edits():
    edits = User.objects(lastedited__exists = True)
    flash("Users that have edited their profile")
    return render_template('edits.html',edits=edits)

@app.route('/notedits')
def notedits():
    query = (Q(lastlogin__gt = dt.datetime(2020,1,1)) & Q(role = "Student")) & (Q(lastedited__exists = False) | Q(adults__exists = False))
    logins = User.objects(query).order_by('lastedited')
    flash("Users that have not edited but have logged in")
    return render_template('logins.html',logins=logins)

@app.route('/compsci')
def compsci():
    students = User.objects(cohort__icontains = 'computer', grade__lt = 13).order_by('lastedited')
    flash("All CompSci Academy students")
    return render_template('logins.html',logins=students)

@app.route('/compsciemails')
def compsciemails():
    emails = []
    csstuds = User.objects(cohort__icontains = "computer", grade__lt = 13)
    for csstud in csstuds:
        emails.append(csstud.aadultemail)
        emails.append(csstud.oemail)
        emails.append(csstud.personalemail)
        for adult in csstud.adults:
            emails.append(adult.email)
            emails.append(adult.altemail)
    dedupedemails = list(set(emails))
    numdups = len(emails) - len(dedupedemails)
    flash(Markup(f"I found a total of {numdups} duplicates for a final set of {len(dedupedemails)}"))

    return render_template('array.html', array=dedupedemails, nested=False)

@app.route('/mmcompsci')
def mmcompsci():
    mmlist = [["Aeries ID","Student Email","Grade","Student fName","Student lName","Parent Names","Parent Emails"]]
    csstuds = User.objects(cohort__icontains = "computer", grade__lt = 13)
    for csstud in csstuds:
        stulist = []
        anames = None
        aemails = None
        stulist.append(csstud.aeriesid)
        stulist.append(csstud.oemail)
        stulist.append(csstud.grade)
        if csstud.ufname and not csstud.ufname == csstud.afname:
            stulist.append(f"{csstud.afname} ({csstud.ufname})")
            stulist.append(csstud.alname)
        else:
            stulist.append(csstud.afname)
            stulist.append(csstud.alname)
        adultisdupe = False
        adultExists = False
        if csstud.adults:
            for adult in csstud.adults:
                if adult.email:
                    adultExists = True
                    if anames:
                        anames = anames + "zzz" + f" {adult.fname} {adult.lname}"
                        aemails = aemails + "zzz" + adult.email
                    else:
                        anames = f" {adult.fname} {adult.lname}"
                        aemails = adult.email
                    if adult.email.lower() == csstud.aadultemail.lower():
                        adultisdupe = True
                
        if adultisdupe == False:
            aadults = csstud.aadults.replace(',', '')
            if anames:
                if not adultExists:
                    anames = anames+"zzz"+aadults
                aemails = aemails + "zzz" + csstud.aadultemail
            else:
                if not adultExists:
                    anames = aadults
                aemails = csstud.aadultemail
        stulist.append(anames)
        stulist.append(aemails)
        del anames
        del aemails
        mmlist.append(stulist)
        
    return render_template('array.html', array=mmlist, nested=True)

@app.route('/alladdresses')
def alladdresses():

    students = User.objects(role__iexact = "student", grade__lt = 13)
    addresses = [["#","Street","City","State","Zip","Cohort"]]
    for i,student in enumerate(students):
        address = [i,student.astreet.replace(',', ''),student.acity,student.astate,student.azipcode]
        if student.cohort:
            address.append(student.cohort.replace(',', ''))
        else:
            address.append("None")
        addresses.append(address)

    return render_template('array.html', array = addresses, nested=True)

@app.route('/groupaddresses', methods=['GET', 'POST'])
def groupaddresses():

    form = SimpleForm()
    parents=""
    mmerge=""

    if form.validate_on_submit():
        students=form.field.data
        stuGroup = students.split(",")
        students = ",".join(stuGroup)
        
        
        for email in stuGroup:
            email=email.strip()
            
            try:
                stu = User.objects.get(oemail=email)
            except:
                if len(email)>1:
                    flash( f"couldn't find {email} in our records")
            mmerge+=f"{stu.aeriesid},{stu.fname} {stu.lname},{email},{email};"

            if stu.aadultemail:
                parents+=f"{stu.aadultemail}, "
                mmerge+=f"{stu.aadultemail};"

            for adult in stu.adults:
                if adult.email:
                    if stu.aadultemail and adult.email != stu.aadultemail:
                        parents+=f"{adult.email}, "
                        mmerge+=f"{adult.email};"
                    elif not stu.aadultemail:
                        parents+=f"{adult.email}, "
                        mmerge+=f"{adult.email};"
            mmerge+="****"
    else:
        parents=None
        students=None

    if request.args.get("emails"):
        form.field.data = request.args.get("emails")
    
    return render_template("groups/groupaddresses.html", form=form, parents=parents,students=students, mmerge=mmerge)

@app.route("/newgroup", methods=['GET','POST'])
def newgroup():
    form = GroupsForm()
    currUser = current_user
    try:
        groups = Group.objects(owner=currUser)
    except:
        groups=None

    if form.validate_on_submit():
        students = form.students.data.split(',')
        studentList = []

        for email in students:
            email=email.strip()
            try:
                stu = User.objects.get(oemail=email)
            except:
                flash(f'{email} is not in the OTData Student database.')
            else:
                studentList.append(stu)

        newGroup = Group(
            owner = currUser,
            name = form.name.data,
            desc = form.desc.data,
            students = studentList
        )
        newGroup.save()
        return redirect(url_for('profile'))

    return render_template('groups/groupnew.html',form=form,groups=groups)

@app.route('/deletegroup/<groupid>')
def deletegroup(groupid):
    try:
        delGroup = Group.objects.get(pk=groupid)
    except:
        flash(f'I could not find the group in the database. ???')
    else:
        delGroup.delete()
        flash(f"the group with id {groupid} has been deleted.")
    
    return redirect(url_for('profile'))

@app.route('/groupmsgto/<groupid>', methods=['GET','POST'])
def groupmsgto(groupid):
    try:
        group = Group.objects.get(pk=groupid)
    except:
        flash(f"That groupd doesn't exist.")
        return redirect(url_for('profile'))

    form = GroupMsgForm()

    if form.validate_on_submit():
        if form.parents.data == True:
            pars=1
        else:
            pars=0
        txtGroupFunc(groupid,form.msg.data,pars)
        flash(f"Message: {form.msg.data} sent to group: {group.name}")

        return redirect(url_for('profile'))

    return render_template('groups/groupmsgto.html',form=form,group=group)



@app.route('/pglist')
def pglist():
    stus = User.objects(cohort__icontains = 'computer', grade__gt = 11, postgrads__exists = True)
    flash(Markup('<b>CS Seniors and alum with PostGrad info --></b>'))
    for stu in stus:
        flash(Markup(f'<a href="/profile/{stu.aeriesid}">{stu.fname} {stu.lname} {stu.grade}</a> ({stu.postgrads[0].type_}: {stu.postgrads[0].org})'))
    stus = User.objects(cohort__icontains = 'computer', grade__gt = 11, postgrads__exists = False)
    flash('')
    flash('')
    flash('')
    flash(Markup('<b>CS Seniors and alum with no PostGrad info--></b>'))
    for stu in stus:
        flash(f'{stu.fname} {stu.lname} {stu.grade}')
    return redirect(url_for('index'))

@app.route('/srinfomm')
def srinfo():
    query = Q(cohort__icontains = 'computer') & Q(grade__gt = 11) & (Q(shirtsize__exists = False) | Q(mobile__exists=False) | Q(ustreet__exists=False) | Q(personalemail__exists = False))
    srs = User.objects(query)
    seniors = [['Name','oemail','pemails','Shirt Size','Personal Email','Mobile','PostGrad','Address']]
    for sr in srs:
        senior = []
        if sr.adults:
            aemails = ""
            for adult in sr.adults:
                if adult.email:
                    aemails += f";{adult.email}"
        srname = ""
        senior.append(f"{sr.fname} {sr.lname}")
        if sr.personalemail:
            senior.append(f"{sr.oemail};{sr.personalemail},{sr.aadultemail};{aemails}")
        else:
            senior.append(f"{sr.oemail},{sr.aadultemail};{aemails}")

        if not sr.shirtsize:
            senior.append("No Shirt Size")
        else:
            senior.append(sr.shirtsize)


        if not sr.personalemail:
            senior.append("No Personal Email")
        else:
            senior.append(sr.personalemail)
        if not sr.mobile:
            senior.append("No Mobile Phone")
        else:
            senior.append(formatphone(sr.mobile))
        if not sr.postgrads:
            senior.append("No PostGrad Info")
        else:
            senior.append(f"{sr.postgrads[0].type_}: {sr.postgrads[0].org}")

        if not sr.ustreet:
            senior.append("No Address Info")
        else:
            senior.append(f"{sr.ustreet} | {sr.ucity} | {sr.ustate} | {sr.uzipcode}")            
        
        seniors.append(senior)
    return render_template('array.html', array=seniors, nested=True)


@app.route('/srssmm')
def srssmm():
    query = Q(cohort__icontains = 'computer') & Q(grade__gt = 11) & Q(shirtsize__exists = False)
    srs = User.objects(query)
    seniors = [['Name','oemail','pemails','Shirt Size','Personal Email','Mobile','PostGrad','Address']]
    for sr in srs:
        senior = []
        aemails = ""
        if sr.adults:
            for adult in sr.adults:
                if adult.email:
                    aemails += f";{adult.email}"
        srname = ""

        senior.append(f"{sr.fname} {sr.lname}")
        if sr.personalemail:
            senior.append(f"{sr.oemail};{sr.personalemail},{sr.aadultemail};{aemails}")
        else:
            senior.append(f"{sr.oemail},{sr.aadultemail};{aemails}")

        if not sr.shirtsize:
            senior.append("No Shirt Size")
        else:
            senior.append(sr.shirtsize)


        if not sr.personalemail:
            senior.append("No Personal Email")
        else:
            senior.append(sr.personalemail)
        if not sr.mobile:
            senior.append("No Mobile Phone")
        else:
            senior.append(formatphone(sr.mobile))
        if not sr.postgrads:
            senior.append("No PostGrad Info")
        else:
            senior.append(f"{sr.postgrads[0].type_}: {sr.postgrads[0].org}")

        if not sr.ustreet:
            senior.append("No Address Info")
        else:
            senior.append(f"{sr.ustreet} | {sr.ucity} | {sr.ustate} | {sr.uzipcode}")            
        
        seniors.append(senior)
    return render_template('array.html', array=seniors, nested=True)

@app.route('/srsmm')
def srsmm():
    query = Q(cohort__icontains = 'computer') & Q(grade__gt = 11)
    srs = User.objects(query)
    seniors = [['Name','oemail','pemails','Shirt Size','Personal Email','Mobile','PostGrad','Address']]
    for sr in srs:
        senior = []
        if sr.adults:
            aemails = ""
            for adult in sr.adults:
                if adult.email:
                    aemails += f";{adult.email}"
        srname = ""

        senior.append(f"{sr.fname} {sr.lname}")
        if sr.personalemail:
            senior.append(f"{sr.oemail};{sr.personalemail},{sr.aadultemail};{aemails}")
        else:
            senior.append(f"{sr.oemail},{sr.aadultemail};{aemails}")

        if not sr.shirtsize:
            senior.append("No Shirt Size")
        else:
            senior.append(sr.shirtsize)


        if not sr.personalemail:
            senior.append("No Personal Email")
        else:
            senior.append(sr.personalemail)
        if not sr.mobile:
            senior.append("No Mobile Phone")
        else:
            senior.append(formatphone(sr.mobile))
        if not sr.postgrads:
            senior.append("No PostGrad Info")
        else:
            senior.append(f"{sr.postgrads[0].type_}: {sr.postgrads[0].org}")

        if not sr.ustreet:
            senior.append("No Address Info")
        else:
            senior.append(f"{sr.ustreet} | {sr.ucity} | {sr.ustate} | {sr.uzipcode}")            
        
        seniors.append(senior)
    return render_template('array.html', array=seniors, nested=True)

@app.route('/mailmerge')
def mailmerge():
    query = Q(cohort__icontains = 'computer') & Q(grade = 10) 
    users = User.objects(query)

    mmlist=[]
    
    for user in users:
        row=[]
        row.append(f'{user.fname} {user.lname}')
        emails=f'{user.oemail};{user.aadultemail}'
        if user.aadultemail:
            emails+=f';{user.aadultemail}'
        if user.personalemail:
            emails+=f';{user.personalemail}'
        if user.adults:
            for adult in user.adults:
                if adult.email:
                    emails+=f';{adult.email}'
        row.append(emails)
    
        mmlist.append(row)
    return render_template('array.html', array=mmlist, nested=True)

@app.route("/csseniors")
def csseniors():
    seniors = User.objects(grade = 12, cohort__icontains = "computer")
    return render_template("seniors.html",students=seniors)