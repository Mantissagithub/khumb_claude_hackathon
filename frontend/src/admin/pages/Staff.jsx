import { useEffect, useState } from "react";
import { Loader2, UserPlus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/shared/components/PageHeader";
import { StatCard } from "@/shared/components/StatCard";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/shared/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { listStaff, createStaff, deleteStaff, analytics } from "@/shared/authApi";

export default function Staff() {
  const [staff, setStaff] = useState([]);
  const [stats, setStats] = useState(null);
  const [form, setForm] = useState({ username: "", password: "", name: "", role: "operator" });
  const [saving, setSaving] = useState(false);

  async function refresh() {
    try {
      const [s, a] = await Promise.all([listStaff(), analytics()]);
      setStaff(s);
      setStats(a);
    } catch (err) {
      toast.error(err.message);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function add(e) {
    e.preventDefault();
    setSaving(true);
    try {
      await createStaff(form);
      toast.success(`Added ${form.username}`);
      setForm({ username: "", password: "", name: "", role: "operator" });
      refresh();
    } catch (err) {
      toast.error(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id, username) {
    if (!confirm(`Remove ${username}?`)) return;
    try {
      await deleteStaff(id);
      toast.success("Removed");
      refresh();
    } catch (err) {
      toast.error(err.message);
    }
  }

  return (
    <>
      <PageHeader
        title="Staff & Analytics"
        description="Admin-only: manage staff accounts and view registry health."
      />

      {stats && (
        <div className="mb-6 grid gap-4 sm:grid-cols-3">
          <StatCard label="Total cases" value={stats.cases_total} tone="navy"
            sublabel={`${stats.cases_by_status?.Active ?? 0} active`} />
          <StatCard label="Reunited" value={stats.cases_by_status?.Reunited ?? 0} tone="forest" />
          <StatCard label="Submissions" value={stats.submissions_total} tone="coral"
            sublabel={`${stats.submissions_by_status?.pending ?? 0} pending review`} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserPlus className="size-4 text-primary" /> Add staff
            </CardTitle>
            <CardDescription>Create an operator or admin account.</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={add} className="space-y-3">
              <div className="space-y-2">
                <Label htmlFor="name">Full name</Label>
                <Input id="name" value={form.name} required
                  onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input id="username" value={form.username} required
                  onChange={(e) => setForm({ ...form, username: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input id="password" type="password" value={form.password} required
                  onChange={(e) => setForm({ ...form, password: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="operator">Operator</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" className="w-full" disabled={saving}>
                {saving && <Loader2 className="size-4 animate-spin" />} Add staff
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card className="border-border bg-card">
          <CardHeader>
            <CardTitle>Staff accounts</CardTitle>
            <CardDescription>{staff.length} account(s).</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Username</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {staff.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell className="font-medium">{s.name}</TableCell>
                    <TableCell className="text-muted-foreground">{s.username}</TableCell>
                    <TableCell className="capitalize text-muted-foreground">{s.role}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon"
                        className="text-danger hover:text-danger"
                        onClick={() => remove(s.id, s.username)}>
                        <Trash2 className="size-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
